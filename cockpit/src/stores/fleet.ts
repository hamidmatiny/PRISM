import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  listAssets,
  listFindings,
  listReviewQueue,
  listWorkOrders,
} from "@/api/controlPlane";
import { queryAllTelemetry } from "@/api/activation";
import type { FleetAssetView, Finding, PendingFinding, WorkOrder } from "@/api/types";
import { assetPosition, computeHealth } from "@/lib/health";

export const useFleetStore = defineStore("fleet", () => {
  const assets = ref<FleetAssetView[]>([]);
  const workOrders = ref<WorkOrder[]>([]);
  const pending = ref<PendingFinding[]>([]);
  const findings = ref<Finding[]>([]);
  const telemetryRows = ref<{ asset_id: string; ping_count: number }[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastRefresh = ref<string | null>(null);

  const byId = computed(() => {
    const m = new Map<string, FleetAssetView>();
    for (const a of assets.value) m.set(a.asset_id, a);
    return m;
  });

  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [assetList, woList, queue, findingList, tele] = await Promise.all([
        listAssets().catch(() => [] as Awaited<ReturnType<typeof listAssets>>),
        listWorkOrders(),
        listReviewQueue(),
        listFindings().catch(() => [] as Finding[]),
        queryAllTelemetry().catch(() => ({ columns: [], rows: [], row_count: 0, warehouse: "" })),
      ]);

      workOrders.value = woList;
      pending.value = queue;
      findings.value = findingList;

      const teleMapped = tele.rows.map((row) => {
        const obj: Record<string, unknown> = {};
        tele.columns.forEach((c, i) => {
          obj[c] = row[i];
        });
        return {
          asset_id: String(obj.asset_id ?? ""),
          ping_count: Number(obj.ping_count ?? 0),
        };
      });
      telemetryRows.value = teleMapped;

      const idSet = new Set<string>();
      for (const a of assetList) idSet.add(a.asset_id);
      for (const w of woList) idSet.add(w.asset_id);
      for (const p of queue) idSet.add(p.asset_id);
      for (const f of findingList) idSet.add(f.asset_id);
      for (const t of teleMapped) if (t.asset_id) idSet.add(t.asset_id);

      const names = new Map(assetList.map((a) => [a.asset_id, a.name || a.asset_id]));
      const statuses = new Map(assetList.map((a) => [a.asset_id, a.status]));

      const sorted = [...idSet].sort();
      assets.value = sorted.map((id, index) => {
        const openWorkOrders = woList.filter(
          (w) => w.asset_id === id && (w.status === "open" || w.status === "in_progress"),
        ).length;
        const unreviewedFindings = queue.filter((p) => p.asset_id === id && !p.reviewed).length;
        return {
          asset_id: id,
          name: names.get(id) || id,
          status: statuses.get(id) || "active",
          health: computeHealth(openWorkOrders, unreviewedFindings),
          openWorkOrders,
          unreviewedFindings,
          position: assetPosition(id, index),
        };
      });
      lastRefresh.value = new Date().toISOString();
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  function workOrdersFor(assetId: string): WorkOrder[] {
    return workOrders.value.filter((w) => w.asset_id === assetId);
  }

  function pendingFor(assetId: string): PendingFinding[] {
    return pending.value.filter((p) => p.asset_id === assetId);
  }

  function findingsFor(assetId: string): Finding[] {
    return findings.value.filter((f) => f.asset_id === assetId);
  }

  return {
    assets,
    workOrders,
    pending,
    findings,
    telemetryRows,
    loading,
    error,
    lastRefresh,
    byId,
    refresh,
    workOrdersFor,
    pendingFor,
    findingsFor,
  };
});
