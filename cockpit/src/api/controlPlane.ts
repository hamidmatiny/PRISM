import { normalizeApiToken } from "@/lib/token";
import type { Asset, Finding, PendingFinding, WorkOrder } from "./types";

const BASE = import.meta.env.VITE_CONTROL_PLANE_URL || "/proxy/control";

function token(): string {
  // Prefer an explicitly saved UI token over any build-time env override.
  const stored = localStorage.getItem("prism_cp_token");
  if (stored) return stored;
  const fromEnv = import.meta.env.VITE_CONTROL_PLANE_TOKEN;
  return typeof fromEnv === "string" ? normalizeApiToken(fromEnv) : "";
}

async function cpFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const tok = token();
  if (!tok) {
    throw new Error(
      `control-plane ${path}: missing API token — paste the viewer token from ` +
        "manage.py print_api_token and click Use token",
    );
  }
  headers.set("Authorization", `Bearer ${tok}`);
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    if (res.status === 401) {
      throw new Error(
        `control-plane ${path}: 401 Unauthorized — token was rejected. ` +
          `Re-copy with: docker compose exec -T control-plane ` +
          `python manage.py print_api_token viewer`,
      );
    }
    throw new Error(`control-plane ${path}: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export function setControlPlaneToken(value: string): string {
  const normalized = normalizeApiToken(value);
  if (!normalized) {
    localStorage.removeItem("prism_cp_token");
    return "";
  }
  localStorage.setItem("prism_cp_token", normalized);
  return normalized;
}

/** Probe auth the same way the cockpit does (Bearer → /api/v1/me). */
export function verifyToken(): Promise<{ username: string; roles: string[] }> {
  return cpFetch("/api/v1/me");
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
