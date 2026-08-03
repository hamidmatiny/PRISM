<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useFleetStore } from "@/stores/fleet";
import { useSelectionStore } from "@/stores/selection";
import { useIncidentEngineStore } from "@/stores/incidentEngine";
import { FleetScene } from "@/three/FleetScene";
import { effectiveHealth } from "@/lib/health";

const canvasRef = ref<HTMLCanvasElement | null>(null);
const backend = ref<"webgpu" | "webgl" | "…">("…");
const fleet = useFleetStore();
const selection = useSelectionStore();
const incidentEngine = useIncidentEngineStore();
const { assets } = storeToRefs(fleet);
const { selectedAssetId } = storeToRefs(selection);
const { breakers } = storeToRefs(incidentEngine);

// Twin render list: same assets, health folded with any live breaker state
// (Phase 15) -- a tripped breaker reads as "critical" on the twin even if
// work orders/findings alone would have called it "ok".
const renderAssets = computed(() => {
  const byAsset = new Map(breakers.value.map((b) => [b.asset_id, b.state]));
  return assets.value.map((a) => ({
    ...a,
    health: effectiveHealth(a.health, byAsset.get(a.asset_id)),
  }));
});

let scene: FleetScene | null = null;

onMounted(async () => {
  if (!canvasRef.value) return;
  scene = new FleetScene(canvasRef.value, (id) => selection.select(id));
  backend.value = await scene.init();
  scene.setAssets(renderAssets.value);
  scene.highlight(selectedAssetId.value);
  scene.start();
  window.addEventListener("resize", onResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onResize);
  scene?.stop();
  scene = null;
});

function onResize() {
  scene?.resize();
}

watch(renderAssets, (list) => scene?.setAssets(list), { deep: true });
watch(selectedAssetId, (id) => scene?.highlight(id));
</script>

<template>
  <div class="viewport">
    <canvas ref="canvasRef" class="canvas" />
    <div class="hud" aria-live="polite">
      <span class="mono">renderer: {{ backend }}</span>
      <span v-if="fleet.loading">refreshing…</span>
      <span v-else>{{ assets.length }} assets</span>
    </div>
  </div>
</template>

<style scoped>
.viewport {
  position: relative;
  flex: 1;
  min-height: 0;
  background: var(--color-bg-0);
}

.canvas {
  width: 100%;
  height: 100%;
  display: block;
  outline: none;
}

.hud {
  position: absolute;
  left: var(--space-3);
  bottom: var(--space-3);
  display: flex;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-3);
  background: color-mix(in srgb, var(--color-bg-1) 85%, transparent);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--color-text-muted);
}
</style>
