import type { Asset, Finding, PendingFinding, WorkOrder } from "./types";

const BASE = import.meta.env.VITE_CONTROL_PLANE_URL || "/proxy/control";

function token(): string {
  return (
    import.meta.env.VITE_CONTROL_PLANE_TOKEN ||
    localStorage.getItem("prism_cp_token") ||
    ""
  );
}

async function cpFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token()}`);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`control-plane ${path}: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export function setControlPlaneToken(value: string): void {
  localStorage.setItem("prism_cp_token", value);
}

export function listAssets(): Promise<Asset[]> {
  return cpFetch("/api/v1/assets");
}

export function listWorkOrders(assetId?: string): Promise<WorkOrder[]> {
  const q = assetId ? `?asset_id=${encodeURIComponent(assetId)}` : "";
  return cpFetch(`/api/v1/work-orders${q}`);
}

export function listReviewQueue(): Promise<PendingFinding[]> {
  return cpFetch("/api/v1/review-queue");
}

export function listFindings(queueStatus?: string): Promise<Finding[]> {
  const q = queueStatus ? `?queue_status=${encodeURIComponent(queueStatus)}` : "";
  return cpFetch(`/api/v1/findings${q}`);
}

export function getFinding(findingId: string): Promise<Finding> {
  return cpFetch(`/api/v1/findings/${encodeURIComponent(findingId)}`);
}

/** Frame URL for <img> — goes through control-plane fixture resolution. */
export function frameUrl(frameRef: string, defectClass: string): string {
  const t = encodeURIComponent(token());
  const dc = encodeURIComponent(defectClass);
  return `${BASE}/api/v1/frames/${encodeURIComponent(frameRef)}?defect_class=${dc}&_auth=${t}`;
}

/** Fetch frame as blob with Authorization (img src cannot set Bearer). */
export async function fetchFrameBlob(frameRef: string, defectClass: string): Promise<string> {
  const headers = new Headers();
  headers.set("Authorization", `Bearer ${token()}`);
  const res = await fetch(
    `${BASE}/api/v1/frames/${encodeURIComponent(frameRef)}?defect_class=${encodeURIComponent(defectClass)}`,
    { headers },
  );
  if (!res.ok) throw new Error(`frame ${frameRef}: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
