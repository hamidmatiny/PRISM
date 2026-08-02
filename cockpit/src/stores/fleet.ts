import { defineStore } from "pinia";
import { computed, ref } from "vue";
import {
  listAssets,
  listFindings,
  listReviewQueue,
  listWorkOrders,
  verifyToken,
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
  const authUser = ref<string | null>(null);
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
      // Auth gate first — previously Promise.all failed on work-orders 401 while
      // listAssets().catch swallowed its own 401, which looked like a WO-only bug.
      const me = await verifyToken();
      authUser.value = me.username;

      const settled = await Promise.allSettled([
        listAssets(),
        listWorkOrders(),
        listReviewQueue(),
        listFindings(),
        queryAllTelemetry(),
      ]);

      const assetList =
        settled[0].status === "fulfilled" ? settled[0].value : ([] as Awaited<ReturnType<typeof listAssets>>);
      const woList =
        settled[1].status === "fulfilled" ? settled[1].value : ([] as WorkOrder[]);
      const queue =
        settled[2].status === "fulfilled" ? settled[2].value : ([] as PendingFinding[]);
      const findingList =
        settled[3].status === "fulfilled" ? settled[3].value : ([] as Finding[]);
      const tele =
        settled[4].status === "fulfilled"
          ? settled[4].value
          : { columns: [] as string[], rows: [] as unknown[][], row_count: 0, warehouse: "" };

      const softFails = settled
        .map((r, i) =>
          r.status === "rejected"
            ? `${["assets", "work-orders", "review-queue", "findings", "telemetry"][i]}: ${
                r.reason instanceof Error ? r.reason.message : String(r.reason)
              }`
            : null,
        )
        .filter(Boolean);
      if (softFails.length && !assetList.length && !queue.length && !findingList.length && !tele.rows.length) {
        throw new Error(softFails.join(" · "));
      }
      if (softFails.length) {
        error.value = `Partial refresh (${me.username}): ${softFails.join(" · ")}`;
      }

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
      authUser.value = null;
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
    authUser,
    lastRefresh,
    byId,
    refresh,
    workOrdersFor,
    pendingFor,
    findingsFor,
  };
});
