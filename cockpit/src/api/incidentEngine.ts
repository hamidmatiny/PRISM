import { withTraceHeaders } from "@/lib/trace";
import type { Breaker, BreakersResponse, Incident, IncidentsResponse, JournalEntry } from "./types";

const BASE = import.meta.env.VITE_INCIDENT_ENGINE_URL || "/proxy/incident";

async function ieFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = withTraceHeaders(new Headers(init.headers));
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`incident-engine ${path}: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function listBreakers(): Promise<Breaker[]> {
  const body = await ieFetch<BreakersResponse>("/breakers");
  return body.breakers;
}

export async function listIncidents(status?: string): Promise<Incident[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  const body = await ieFetch<IncidentsResponse>(`/incidents${q}`);
  return body.incidents;
}

export async function acknowledgeIncident(incidentId: string): Promise<Incident> {
  return ieFetch<Incident>(`/incidents/${encodeURIComponent(incidentId)}/acknowledge`, {
    method: "POST",
  });
}

export async function resolveIncident(incidentId: string): Promise<Incident> {
  return ieFetch<Incident>(`/incidents/${encodeURIComponent(incidentId)}/resolve`, {
    method: "POST",
  });
}

export async function journalTail(limit = 100): Promise<JournalEntry[]> {
  const body = await ieFetch<{ count: number; entries: JournalEntry[] }>(
    `/v1/journal?limit=${limit}`,
  );
  return body.entries;
}

export interface ScenarioRunResult {
  seed: number;
  scenario_id: string;
  journal_path: string;
  ticks_requested: number;
  elapsed_seconds: number;
  emitted: number;
  accepted: number;
  rejected: number;
  skipped: number;
  by_corruption_type: Record<string, number>;
}

/** Runs against ingestion's admin endpoint (Phase 15), not incident-engine directly --
 * ingestion resets scenario-engine to the given seed and drives real ticks through the
 * real validate -> bronze/DLQ -> incident-engine-report path. */
const INGESTION_BASE = import.meta.env.VITE_INGESTION_URL || "/proxy/ingestion";

export async function runScenario(
  seed: number,
  opts: { ticks?: number; rate_hz?: number } = {},
): Promise<ScenarioRunResult> {
  const headers = withTraceHeaders(new Headers({ "content-type": "application/json" }));
  const res = await fetch(`${INGESTION_BASE}/v1/scenario-runs`, {
    method: "POST",
    headers,
    body: JSON.stringify({ seed, ticks: opts.ticks ?? 30, rate_hz: opts.rate_hz ?? 3.0 }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`ingestion /v1/scenario-runs: ${res.status} ${body}`);
  }
  return res.json() as Promise<ScenarioRunResult>;
}
