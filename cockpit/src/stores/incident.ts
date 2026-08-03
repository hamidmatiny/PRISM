import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";
import type { IncidentEvent } from "@/api/types";
import { useFleetStore } from "./fleet";
import { useIncidentEngineStore } from "./incidentEngine";

/**
 * Incident scrubber timeline built from real control-plane / activation data:
 * CV findings (detected_at) → work orders (created_at) → telemetry snapshot markers.
 */
export const useIncidentStore = defineStore("incident", () => {
  const events = ref<IncidentEvent[]>([]);
  const cursorMs = ref(0);
  const playing = ref(false);
  const speed = ref(1);
  let raf = 0;
  let lastTs = 0;

  const tMin = computed(() => (events.value.length ? events.value[0].t : 0));
  const tMax = computed(() =>
    events.value.length ? events.value[events.value.length - 1].t : 0,
  );
  const progress = computed(() => {
    const span = tMax.value - tMin.value;
    if (span <= 0) return 0;
    return (cursorMs.value - tMin.value) / span;
  });

  const activeEvent = computed(() => {
    let current: IncidentEvent | null = null;
    for (const e of events.value) {
      if (e.t <= cursorMs.value) current = e;
      else break;
    }
    return current;
  });

  function rebuild(): void {
    const fleet = useFleetStore();
    const list: IncidentEvent[] = [];

    for (const p of fleet.pending) {
      const iso = p.detected_at;
      if (!iso) continue;
      list.push({
        id: `cv-${p.finding_id}`,
        t: Date.parse(iso),
        kind: "cv_finding",
        asset_id: p.asset_id,
        label: `CV ${p.defect_class} (${(p.confidence * 100).toFixed(0)}%)`,
        payload: { ...p },
      });
    }
    for (const f of fleet.findings) {
      list.push({
        id: `cvf-${f.finding_id}`,
        t: Date.parse(f.detected_at),
        kind: "cv_finding",
        asset_id: f.asset_id,
        label: `Finding ${f.defect_class} · ${f.queue_status}`,
        payload: { ...f },
      });
    }
    for (const w of fleet.workOrders) {
      list.push({
        id: `wo-${w.work_order_id}`,
        t: Date.parse(w.created_at),
        kind: "work_order",
        asset_id: w.asset_id,
        label: `WO ${w.status}: ${w.title}`,
        payload: { ...w },
      });
    }
    const ieStore = useIncidentEngineStore();
    for (const j of ieStore.journal) {
      if (j.event !== "breaker_transition" && j.event !== "incident_opened") continue;
      const iso = j.at;
      const state = typeof j.detail.state === "string" ? j.detail.state : j.event;
      list.push({
        id: `brk-${j.asset_id}-${iso}-${j.event}`,
        t: Date.parse(iso),
        kind: "breaker",
        asset_id: j.asset_id,
        label: `Breaker ${state}`,
        payload: { ...j.detail, event: j.event },
      });
    }

    // Telemetry anchors — place at mid-window so scrubber shows sensor context.
    if (list.length && fleet.telemetryRows.length) {
      const mid = list.reduce((s, e) => s + e.t, 0) / list.length;
      for (const row of fleet.telemetryRows) {
        list.push({
          id: `tel-${row.asset_id}`,
          t: mid,
          kind: "telemetry",
          asset_id: row.asset_id,
          label: `Telemetry ping_count=${row.ping_count}`,
          payload: { ...row },
        });
      }
    }

    list.sort((a, b) => a.t - b.t);
    // Deduplicate by id
    const seen = new Set<string>();
    events.value = list.filter((e) => {
      if (seen.has(e.id)) return false;
      seen.add(e.id);
      return Number.isFinite(e.t);
    });
    if (events.value.length) {
      cursorMs.value = events.value[0].t;
    }
  }

  function setProgress(p: number): void {
    const span = tMax.value - tMin.value;
    cursorMs.value = tMin.value + Math.min(1, Math.max(0, p)) * span;
  }

  function tick(now: number): void {
    if (!playing.value) return;
    if (lastTs) {
      const dt = (now - lastTs) * speed.value;
      // 1 real second → 30 incident seconds at speed=1
      cursorMs.value = Math.min(tMax.value, cursorMs.value + dt * 30);
      if (cursorMs.value >= tMax.value) {
        playing.value = false;
      }
    }
    lastTs = now;
    raf = requestAnimationFrame(tick);
  }

  function play(): void {
    if (playing.value) return;
    playing.value = true;
    lastTs = 0;
    raf = requestAnimationFrame(tick);
  }

  function pause(): void {
    playing.value = false;
    cancelAnimationFrame(raf);
  }

  function toggle(): void {
    if (playing.value) pause();
    else play();
  }

  const fleet = useFleetStore();
  watch(
    () => fleet.lastRefresh,
    () => rebuild(),
  );
  const ieStoreForWatch = useIncidentEngineStore();
  watch(
    () => ieStoreForWatch.lastRefresh,
    () => rebuild(),
  );

  return {
    events,
    cursorMs,
    playing,
    speed,
    tMin,
    tMax,
    progress,
    activeEvent,
    rebuild,
    setProgress,
    play,
    pause,
    toggle,
  };
});
