<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { fetchFrameBlob } from "@/api/controlPlane";
import type { BoundingBox, PendingFinding } from "@/api/types";

const props = defineProps<{ finding: PendingFinding | null }>();
const src = ref<string | null>(null);
const err = ref<string | null>(null);
let objectUrl: string | null = null;

const box = computed<BoundingBox | null>(() => props.finding?.bounding_box ?? null);

async function load() {
  err.value = null;
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  src.value = null;
  if (!props.finding) return;
  try {
    objectUrl = await fetchFrameBlob(props.finding.frame_ref, props.finding.defect_class);
    src.value = objectUrl;
  } catch (e) {
    err.value = e instanceof Error ? e.message : String(e);
  }
}

onMounted(load);
watch(() => props.finding?.finding_id, load);
onUnmounted(() => {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
});

/** Overlay assumes fixture PNGs are 320×240 (cv-service fixture generator). */
const FRAME_W = 320;
const FRAME_H = 240;
const boxStyle = computed(() => {
  if (!box.value) return null;
  return {
    left: `${(box.value.x / FRAME_W) * 100}%`,
    top: `${(box.value.y / FRAME_H) * 100}%`,
    width: `${(box.value.width / FRAME_W) * 100}%`,
    height: `${(box.value.height / FRAME_H) * 100}%`,
  };
});
</script>

<template>
  <section class="cv" aria-label="CV finding frame with bounding box">
    <header>
      <h3>CV finding</h3>
      <span v-if="finding" class="mono muted">
        {{ finding.defect_class }} · conf {{ (finding.confidence * 100).toFixed(0) }}%
      </span>
    </header>
    <p v-if="!finding" class="muted">No unreviewed finding for this asset.</p>
    <p v-else-if="err" class="err" role="alert">{{ err }}</p>
    <div v-else class="frame-wrap">
      <img v-if="src" :src="src" :alt="`Frame ${finding?.frame_ref}`" width="320" height="240" />
      <div
        v-if="boxStyle"
        class="bbox"
        :style="boxStyle"
        :title="finding?.defect_class"
        role="presentation"
      />
    </div>
  </section>
</template>

<style scoped>
.cv {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

h3 {
  font-size: var(--text-sm);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.muted {
  color: var(--color-text-dim);
  font-size: var(--text-xs);
}

.err {
  color: var(--color-critical);
  font-size: var(--text-sm);
}

.frame-wrap {
  position: relative;
  width: 100%;
  max-width: 320px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: #000;
}

img {
  display: block;
  width: 100%;
  height: auto;
}

.bbox {
  position: absolute;
  border: 2px solid var(--color-critical);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.6);
  pointer-events: none;
}
</style>
