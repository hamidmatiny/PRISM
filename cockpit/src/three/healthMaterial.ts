import { Color, MeshStandardNodeMaterial } from "three/webgpu";
import { color as tslColor, float, mix, mul, oscSine, time, uniform, vec3 } from "three/tsl";
import type { HealthLevel } from "@/api/types";
import { healthColor } from "@/lib/health";

/**
 * TSL health material — emissive pulse scales with severity.
 * One code path for WebGPU and WebGL backends (no hand-written GLSL/WGSL).
 */
export function createHealthMaterial(level: HealthLevel): MeshStandardNodeMaterial {
  const hex = healthColor(level);
  const base = new Color(hex);
  const pulseAmt = level === "ok" ? 0.08 : level === "warn" ? 0.35 : 0.7;
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const uPulse = uniform(reduced ? 0 : pulseAmt);
  const uBase = uniform(base);

  const material = new MeshStandardNodeMaterial();
  material.colorNode = tslColor(uBase);
  material.roughness = 0.45;
  material.metalness = 0.25;

  const pulse = mul(oscSine(mul(time, float(2.2))), uPulse);
  material.emissiveNode = mix(vec3(0, 0, 0), tslColor(uBase), pulse);

  return material;
}
