<script setup lang="ts">
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useFleetStore } from "@/stores/fleet";
import { useSelectionStore } from "@/stores/selection";
import TelemetryChart from "./TelemetryChart.vue";
import CvFrameOverlay from "./CvFrameOverlay.vue";
import WorkOrderList from "./WorkOrderList.vue";
import { healthColor } from "@/lib/health";

const fleet = useFleetStore();
const selection = useSelectionStore();
const { selectedAssetId, panelOpen } = storeToRefs(selection);

const asset = computed(() =>
  selectedAssetId.value ? fleet.byId.get(selectedAssetId.value) ?? null : null,
);
const orders = computed(() =>
  selectedAssetId.value ? fleet.workOrdersFor(selectedAssetId.value) : [],
);
const topFinding = computed(() => {
  if (!selectedAssetId.value) return null;
  return fleet.pendingFor(selectedAssetId.value)[0] ?? null;
});

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") selection.closePanel();
}
</script>

<template>
  <aside
    v-if="panelOpen && asset"
    class="panel"
    role="dialog"
    aria-modal="false"
    :aria-label="`Asset ${asset.asset_id}`"
    tabindex="-1"
    @keydown="onKeydown"
  >
    <header class="panel-head">
      <div>
        <p class="eyebrow mono">{{ asset.asset_id }}</p>
        <h2>{{ asset.name }}</h2>
      </div>
      <button type="button" class="close" aria-label="Close detail panel" @click="selection.closePanel()">
        Esc
      </button>
    </header>

    <div class="health" :style="{ '--h': healthColor(asset.health) }">
      <span class="dot" aria-hidden="true" />
      <span>
        Health <strong class="mono">{{ asset.health }}</strong>
        · {{ asset.openWorkOrders }} open WO
        · {{ asset.unreviewedFindings }} unreviewed CV
      </span>
    </div>

    <div class="body">
      <TelemetryChart :asset-id="asset.asset_id" />
      <CvFrameOverlay :finding="topFinding" />
      <WorkOrderList :orders="orders" />
    </div>
  </aside>
</template>

<style scoped>
.panel {
  position: absolute;
  top: var(--header-height);
  right: 0;
  bottom: var(--scrubber-height);
  width: var(--panel-width);
  background: color-mix(in srgb, var(--color-bg-1) 94%, transparent);
  border-left: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  z-index: 5;
  backdrop-filter: blur(8px);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.eyebrow {
  margin: 0 0 var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-accent);
}

h2 {
  font-size: var(--text-lg);
}

.close {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.health {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  background: var(--h);
  box-shadow: 0 0 12px var(--h);
}

.body {
  overflow: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}
</style>
