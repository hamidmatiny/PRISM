import { withTraceHeaders } from "@/lib/trace";
import type { QueryResponse } from "./types";

const BASE = import.meta.env.VITE_ACTIVATION_URL || "/proxy/activation";

/**
 * Ensure gold table is activated (idempotent) so /v1/query warehouse=auto works.
 * Shape matches contracts/activation-contract ActivateRequest (gold_uri required).
 * Compose lakehouse gold is at file:///data/lakehouse/gold/<table>; fixtures are
 * the documented fallback when lakehouse gold is empty.
 */
export async function ensureActivated(table = "asset_daily_metrics"): Promise<void> {
  const candidates = [
    import.meta.env.VITE_GOLD_URI as string | undefined,
    `file:///data/lakehouse/gold/${table}`,
    `file:///app/activation-gateway/fixtures/gold/${table}`,
  ].filter((u): u is string => Boolean(u));

  for (const gold_uri of candidates) {
    const headers = withTraceHeaders(new Headers({ "content-type": "application/json" }));
    const res = await fetch(`${BASE}/v1/activate`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        gold_table: table,
        warehouse: "redshift",
        gold_uri,
        set_primary: true,
      }),
    });
    if (res.ok || res.status === 409) return;
  }
}

export async function queryGold(sql: string, table = "asset_daily_metrics"): Promise<QueryResponse> {
  await ensureActivated(table);
  const headers = withTraceHeaders(new Headers({ "content-type": "application/json" }));
  const res = await fetch(`${BASE}/v1/query`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      table,
      warehouse: "auto",
      sql,
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`activation-gateway query: ${res.status} ${body}`);
  }
  return res.json() as Promise<QueryResponse>;
}

/** Telemetry for one asset via the real activation-gateway query contract. */
export async function queryAssetTelemetry(assetId: string): Promise<QueryResponse> {
  // Columns match activation-gateway fixtures / lakehouse gold asset_daily_metrics.
  const sql =
    `SELECT asset_id, ping_count FROM asset_daily_metrics ` +
    `WHERE asset_id = '${assetId.replace(/'/g, "")}' ORDER BY asset_id`;
  return queryGold(sql);
}

export async function queryAllTelemetry(): Promise<QueryResponse> {
  return queryGold(
    "SELECT asset_id, ping_count FROM asset_daily_metrics ORDER BY asset_id",
  );
}
