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

export type IncidentKind = "telemetry" | "cv_finding" | "work_order";

export interface IncidentEvent {
  id: string;
  t: number;
  kind: IncidentKind;
  asset_id: string;
  label: string;
  payload: Record<string, unknown>;
}
