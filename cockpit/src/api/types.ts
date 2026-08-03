/** Shapes matching control-plane / activation-gateway responses (Phase 5 / 4). */

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Asset {
  asset_id: string;
  name: string;
  status: string;
}

export interface WorkOrder {
  work_order_id: string;
  asset_id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
}

export interface PendingFinding {
  finding_id: string;
  asset_id: string;
  defect_class: string;
  confidence: number;
  frame_ref: string;
  reason: string;
  queue: string;
  path: string;
  reviewed: boolean;
  bounding_box: BoundingBox | null;
  detected_at: string | null;
}

export interface Finding {
  finding_id: string;
  asset_id: string;
  defect_class: string;
  confidence: number;
  queue_status: string;
  reviewed: boolean;
  gold_path: string;
  frame_ref: string;
  detected_at: string;
  bounding_box: BoundingBox | null;
}

export interface QueryResponse {
  warehouse: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
}

export type HealthLevel = "ok" | "warn" | "critical" | "unknown";

export interface FleetAssetView {
  asset_id: string;
  name: string;
  status: string;
  health: HealthLevel;
  openWorkOrders: number;
  unreviewedFindings: number;
  position: [number, number, number];
}

export type IncidentKind = "telemetry" | "cv_finding" | "work_order" | "breaker";

export interface IncidentEvent {
  id: string;
  t: number;
  kind: IncidentKind;
  asset_id: string;
  label: string;
  payload: Record<string, unknown>;
}

/** incident-engine (Phase 14/15) — per-asset circuit breaker. */
export type BreakerState = "closed" | "open" | "half_open";

export interface Breaker {
  asset_id: string;
  state: BreakerState;
  incident_id: string | null;
  trip_reason: string | null;
  quarantine_rate: number | null;
  consecutive_qa_failures: number;
  drifted_feature_count: number;
  opened_at: string | null;
  last_transition_at: string;
}

export interface BreakersResponse {
  count: number;
  breakers: Breaker[];
}

export type IncidentStatus = "open" | "acknowledged" | "resolved";

export interface Incident {
  incident_id: string;
  asset_id: string;
  trigger: string;
  status: IncidentStatus;
  trip_count: number;
  opened_at: string;
  last_transition_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface IncidentsResponse {
  count: number;
  incidents: Incident[];
}

export interface JournalEntry {
  asset_id: string;
  at: string;
  event: "observation" | "breaker_transition" | "incident_opened" | "incident_acknowledged" | "incident_resolved";
  detail: Record<string, unknown>;
}
