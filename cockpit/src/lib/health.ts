import type { BreakerState, HealthLevel } from "@/api/types";

/** Room-readable health from open work orders + unreviewed CV findings. */
export function computeHealth(openWorkOrders: number, unreviewedFindings: number): HealthLevel {
  if (openWorkOrders > 0 && unreviewedFindings > 0) return "critical";
  if (openWorkOrders > 0 || unreviewedFindings > 0) return "warn";
  return "ok";
}

export function healthColor(level: HealthLevel): string {
  switch (level) {
    case "critical":
      return "#ff4d3a";
    case "warn":
      return "#f0b429";
    case "ok":
      return "#3ecf7a";
    default:
      return "#6b7c8f";
  }
}

/**
 * Fold a live circuit-breaker state into the asset's rendered health level
 * (Phase 15) -- an open breaker is a "degraded" signal everywhere in the
 * cockpit (twin glow, detail panel), not just on the Breaker Board itself.
 * Never downgrades an already-worse level computed from WOs/findings.
 */
export function effectiveHealth(base: HealthLevel, breaker: BreakerState | undefined): HealthLevel {
  if (breaker === "open") return "critical";
  if (breaker === "half_open" && base === "ok") return "warn";
  return base;
}

/** Deterministic grid position from asset_id for the twin floor plan. */
export function assetPosition(assetId: string, index: number): [number, number, number] {
  const cols = 4;
  const col = index % cols;
  const row = Math.floor(index / cols);
  // Slight hash jitter so IDs do not look like a spreadsheet.
  let h = 0;
  for (let i = 0; i < assetId.length; i++) h = (h * 31 + assetId.charCodeAt(i)) | 0;
  const jx = ((h % 7) - 3) * 0.08;
  const jz = (((h >> 3) % 7) - 3) * 0.08;
  return [col * 3.2 - 4.8 + jx, 0.6, row * 3.2 - 3.2 + jz];
}
