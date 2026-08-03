<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useIncidentEngineStore } from "@/stores/incidentEngine";
import { useSelectionStore } from "@/stores/selection";
import type { Breaker, BreakerState } from "@/api/types";

const store = useIncidentEngineStore();
const selection = useSelectionStore();
const open = ref(false);
let poll: ReturnType<typeof setInterval> | null = null;

const STATE_ORDER: Record<BreakerState, number> = { open: 0, half_open: 1, closed: 2 };

const sorted = computed(() =>
  [...store.breakers].sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state]),
);

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - Date.parse(iso);
  if (!Number.isFinite(ms)) return "—";
  if (ms < 1000) return "just now";
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  return `${Math.round(ms / 3_600_000)}h ago`;
}

function stateLabel(b: Breaker): string {
  if (b.state === "open") return "TRIPPED";
  if (b.state === "half_open") return "PROBING";
  return "CLOSED";
}

function reason(b: Breaker): string {
  if (b.state === "closed") return "nominal";
  const bits: string[] = [];
  if (b.trip_reason) bits.push(b.trip_reason);
  if (b.quarantine_rate !== null) bits.push(`quarantine ${(b.quarantine_rate * 100).toFixed(0)}%`);
  if (b.drifted_feature_count) bits.push(`${b.drifted_feature_count} drifted features`);
  return bits.join(" · ") || "unspecified";
}

function focusAsset(assetId: string) {
  selection.select(assetId);
}

function startPoll() {
  if (poll) return;
  void store.refresh();
  poll = setInterval(() => void store.refresh(), 3000);
}

function stopPoll() {
  if (poll) clearInterval(poll);
  poll = null;
}

watch(open, (v) => (v ? startPoll() : stopPoll()));
onMounted(() => {
  if (open.value) startPoll();
});
onUnmounted(stopPoll);
</script>

<template>
  <div class="board" :data-open="open">
    <button
      type="button"
      class="toggle"
      :class="{ alert: store.openCount() > 0 }"
      :aria-expanded="open"
      @click="open = !open"
    >
      Breaker Board
      <span v-if="store.openCount()" class="badge mono">{{ store.openCount() }}</span>
    </button>

    <section v-if="open" class="panel" aria-label="Circuit breaker board">
      <header>
        <h2>Circuit breakers</h2>
        <p class="muted">
          Per-asset ingestion breaker state, live from incident-engine.
          <span v-if="!store.available" class="err"> · unreachable — showing last known state</span>
        </p>
      </header>

      <p v-if="!sorted.length" class="empty muted">
        No breaker state reported yet — run a scenario or wait for telemetry.
      </p>

      <ul v-else class="grid" role="list">
        <li
          v-for="b in sorted"
          :key="b.asset_id"
          class="card"
          :data-state="b.state"
          @click="focusAsset(b.asset_id)"
        >
          <div class="card-head">
            <span class="dot" aria-hidden="true" />
            <strong class="state">{{ stateLabel(b) }}</strong>
          </div>
          <p class="asset mono">{{ b.asset_id }}</p>
          <p class="reason">{{ reason(b) }}</p>
          <p class="meta mono">
            {{ b.consecutive_qa_failures }} fails · {{ relativeTime(b.last_transition_at) }}
          </p>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.board {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  z-index: 6;
  max-width: min(40rem, calc(100% - 2rem));
}

.toggle {
  position: relative;
  font-weight: var(--weight-semibold);
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-strong);
  color: var(--color-text);
}

.toggle.alert {
  border-color: var(--color-critical);
  color: var(--color-critical);
  animation: pulse-border 1.6s ease-in-out infinite;
}

.badge {
  margin-left: var(--space-2);
  padding: 0 0.4em;
  border-radius: 999px;
  background: var(--color-critical);
  color: #1a0805;
  font-size: var(--text-xs);
}

.panel {
  margin-top: var(--space-2);
  padding: var(--space-4);
  background: color-mix(in srgb, var(--color-bg-1) 94%, transparent);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: min(70vh, 34rem);
  overflow: auto;
}

h2 {
  font-size: var(--text-md);
  margin: 0;
}

.muted {
  margin: var(--space-1) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-dim);
}

.err {
  color: var(--color-critical);
}

.empty {
  margin: 0;
}

.grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
  gap: var(--space-3);
}

.card {
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-bg-0);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: transform 0.1s ease;
}

.card:hover {
  transform: translateY(-1px);
  border-color: var(--color-border-strong);
}

.card-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.dot {
  width: 0.7rem;
  height: 0.7rem;
  border-radius: 50%;
  background: var(--color-ok);
  box-shadow: 0 0 8px var(--color-ok);
  flex-shrink: 0;
}

.state {
  font-size: var(--text-sm);
  letter-spacing: 0.06em;
  color: var(--color-ok);
}

.card[data-state="half_open"] .dot,
.card[data-state="half_open"] .state {
  color: var(--color-warn);
}
.card[data-state="half_open"] .dot {
  background: var(--color-warn);
  box-shadow: 0 0 8px var(--color-warn);
}

.card[data-state="open"] {
  border-color: var(--color-critical);
  animation: pulse-card 1.6s ease-in-out infinite;
}
.card[data-state="open"] .dot,
.card[data-state="open"] .state {
  color: var(--color-critical);
}
.card[data-state="open"] .dot {
  background: var(--color-critical);
  box-shadow: 0 0 10px var(--color-critical);
}

.asset {
  margin: 0 0 var(--space-1);
  font-size: var(--text-sm);
  color: var(--color-text);
}

.reason {
  margin: 0 0 var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-dim);
  min-height: 2.4em;
}

.meta {
  margin: 0;
  font-size: 0.7rem;
  color: var(--color-text-dim);
}

@keyframes pulse-card {
  0%,
  100% {
    box-shadow: 0 0 0 rgba(255, 77, 58, 0);
  }
  50% {
    box-shadow: 0 0 16px color-mix(in srgb, var(--color-critical) 55%, transparent);
  }
}

@keyframes pulse-border {
  0%,
  100% {
    box-shadow: 0 0 0 rgba(255, 77, 58, 0);
  }
  50% {
    box-shadow: 0 0 10px color-mix(in srgb, var(--color-critical) 60%, transparent);
  }
}
</style>
