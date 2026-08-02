<script setup lang="ts">
import { computed, watch } from "vue";
import { storeToRefs } from "pinia";
import { useIncidentStore } from "@/stores/incident";
import { useSelectionStore } from "@/stores/selection";

const incident = useIncidentStore();
const selection = useSelectionStore();
const { events, playing, progress, activeEvent, cursorMs, tMin, tMax } = storeToRefs(incident);

const label = computed(() => {
  if (!activeEvent.value) return "No incident window yet — refresh fleet data.";
  return `${activeEvent.value.kind}: ${activeEvent.value.label}`;
});

const timeLabel = computed(() => {
  if (!events.value.length) return "—";
  return new Date(cursorMs.value).toISOString();
});

watch(activeEvent, (ev) => {
  if (ev?.asset_id) selection.select(ev.asset_id);
});

function onInput(e: Event) {
  const v = Number((e.target as HTMLInputElement).value);
  incident.setProgress(v);
}
</script>

<template>
  <section class="scrubber" aria-label="Incident time scrubber">
    <div class="meta">
      <strong>Incident replay</strong>
      <span class="mono muted">{{ timeLabel }}</span>
      <span class="event" :data-kind="activeEvent?.kind || 'none'">{{ label }}</span>
    </div>
    <div class="controls">
      <button type="button" :aria-pressed="playing" @click="incident.toggle()">
        {{ playing ? "Pause" : "Play" }}
      </button>
      <input
        class="range"
        type="range"
        min="0"
        max="1"
        step="0.001"
        :value="progress"
        :disabled="!events.length"
        :aria-valuetext="label"
        aria-label="Scrub incident timeline"
        @input="onInput"
      />
      <span class="mono muted">{{ events.length }} events</span>
    </div>
    <ol class="ticks" aria-hidden="true">
      <li
        v-for="e in events"
        :key="e.id"
        :data-kind="e.kind"
        :style="{
          left: `${tMax === tMin ? 0 : ((e.t - tMin) / (tMax - tMin)) * 100}%`,
        }"
      />
    </ol>
  </section>
</template>

<style scoped>
.scrubber {
  height: var(--scrubber-height);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-1);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  position: relative;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: baseline;
  font-size: var(--text-sm);
}

.muted {
  color: var(--color-text-dim);
  font-size: var(--text-xs);
}

.event {
  color: var(--color-text);
}

.event[data-kind="cv_finding"] {
  color: var(--color-critical);
}

.event[data-kind="work_order"] {
  color: var(--color-warn);
}

.event[data-kind="telemetry"] {
  color: var(--color-accent);
}

.controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.range {
  flex: 1;
  accent-color: var(--color-accent);
}

.ticks {
  position: absolute;
  left: var(--space-4);
  right: var(--space-4);
  bottom: var(--space-2);
  height: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ticks li {
  position: absolute;
  top: 0;
  width: 2px;
  height: 4px;
  background: var(--color-text-dim);
}

.ticks li[data-kind="cv_finding"] {
  background: var(--color-critical);
}

.ticks li[data-kind="work_order"] {
  background: var(--color-warn);
}

.ticks li[data-kind="telemetry"] {
  background: var(--color-accent);
}
</style>
