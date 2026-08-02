import { WebGPURenderer } from "three/webgpu";
import type { WebGPURenderer as WebGPURendererType } from "three/webgpu";

export type TwinRenderer = WebGPURendererType;

/**
 * WebGPURenderer with automatic WebGL backend fallback (three/webgpu).
 * Custom look uses TSL node materials — not hand-written GLSL/WGSL.
 */
export async function createTwinRenderer(
  canvas: HTMLCanvasElement,
): Promise<{ renderer: TwinRenderer; backend: "webgpu" | "webgl" }> {
  const renderer = new WebGPURenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  await renderer.init();

  // three.js exposes the active backend after init.
  const backendName = (renderer.backend?.constructor?.name || "").toLowerCase();
  const backend: "webgpu" | "webgl" = backendName.includes("webgpu") ? "webgpu" : "webgl";
  return { renderer, backend };
}
