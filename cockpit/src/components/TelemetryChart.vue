<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { queryAssetTelemetry } from "@/api/activation";

const props = defineProps<{ assetId: string }>();
const error = ref<string | null>(null);
const rows = ref<{ label: string; value: number }[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await queryAssetTelemetry(props.assetId);
    rows.value = res.rows.map((r, i) => {
      const obj: Record<string, unknown> = {};
      res.columns.forEach((c, idx) => {
        obj[c] = r[idx];
      });
      return {
        label: String(obj.asset_id ?? `row-${i}`),
        value: Number(obj.ping_count ?? 0),
      };
    });
    if (!rows.value.length) {
      // Still show a zero bar so empty warehouse results are visible.
      rows.value = [{ label: props.assetId, value: 0 }];
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.assetId, load);

const max = computed(() => Math.max(1, ...rows.value.map((r) => r.value)));
</script>

<template>
  <section class="chart" aria-label="Telemetry from activation-gateway">
    <header>
      <h3>Telemetry</h3>
      <span class="mono muted">POST /v1/query · asset_daily_metrics</span>
    </header>
    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="error" class="err" role="alert">{{ error }}</p>
    <ul v-else class="bars">
      <li v-for="r in rows" :key="r.label">
        <span class="mono label">{{ r.label }}</span>
        <div class="track" role="img" :aria-label="`ping_count ${r.value}`">
          <div class="fill" :style="{ width: `${(r.value / max) * 100}%` }" />
        </div>
        <span class="mono val">{{ r.value }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.chart {
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

.bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.bars li {
  display: grid;
  grid-template-columns: 7rem 1fr 3rem;
  gap: var(--space-2);
  align-items: center;
}

.label {
  font-size: var(--text-xs);
  overflow: hidden;
  text-overflow: ellipsis;
}

.track {
  height: 0.65rem;
  background: var(--color-bg-0);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  overflow: hidden;
}

.fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent-dim), var(--color-accent));
  transition: width var(--motion-med) var(--ease-out);
}

.val {
  font-size: var(--text-xs);
  text-align: right;
}
</style>
