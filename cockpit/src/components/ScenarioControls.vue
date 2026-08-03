<script setup lang="ts">
import { ref } from "vue";
import { runScenario, type ScenarioRunResult } from "@/api/incidentEngine";
import { useIncidentEngineStore } from "@/stores/incidentEngine";
import { useFleetStore } from "@/stores/fleet";
import { useIncidentStore } from "@/stores/incident";

const ieStore = useIncidentEngineStore();
const fleet = useFleetStore();
const incident = useIncidentStore();

const open = ref(false);
const seed = ref(Math.floor(Math.random() * 100000));
const ticks = ref(30);
const rateHz = ref(3);
const running = ref(false);
const error = ref<string | null>(null);
const result = ref<ScenarioRunResult | null>(null);

async function launch() {
  running.value = true;
  error.value = null;
  result.value = null;
  try {
    result.value = await runScenario(seed.value, { ticks: ticks.value, rate_hz: rateHz.value });
    // A scenario batch produces real bronze/DLQ writes and real breaker observations —
    // pull every downstream view up to date once the batch is done.
    await Promise.all([fleet.refresh(), ieStore.refresh()]);
    incident.rebuild();
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    running.value = false;
  }
}

function reseed() {
  seed.value = Math.floor(Math.random() * 100000);
}
</script>

<template>
  <div class="controls" :data-open="open">
    <button type="button" class="toggle" :aria-expanded="open" @click="open = !open">
      Scenario controls
    </button>

    <section v-if="open" class="panel" aria-label="Scenario controls">
      <header>
        <h2>Run a scenario</h2>
        <p class="muted">
          Resets scenario-engine to a seed, then drives real ticks through ingestion
          (bronze/DLQ + incident-engine) — same code path the live pipeline uses.
        </p>
      </header>

      <form class="form" @submit.prevent="launch">
        <label class="field">
          <span class="mono">seed</span>
          <input v-model.number="seed" class="mono" type="number" min="0" step="1" />
        </label>
        <button type="button" class="link" :disabled="running" @click="reseed">
          randomize
        </button>
        <label class="field">
          <span class="mono">ticks</span>
          <input v-model.number="ticks" class="mono" type="number" min="1" max="300" step="1" />
        </label>
        <label class="field">
          <span class="mono">rate_hz</span>
          <input v-model.number="rateHz" class="mono" type="number" min="0.5" max="20" step="0.5" />
        </label>
        <button type="submit" :disabled="running">
          {{ running ? "Running…" : "Launch batch" }}
        </button>
      </form>

      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <article v-if="result" class="result">
        <p class="mono">
          seed={{ result.seed }} · scenario_id={{ result.scenario_id }}
        </p>
        <p class="mono">
          emitted={{ result.emitted }} accepted={{ result.accepted }}
          rejected={{ result.rejected }} skipped={{ result.skipped }}
          · {{ result.elapsed_seconds.toFixed(1) }}s
        </p>
        <p v-if="Object.keys(result.by_corruption_type).length" class="mono muted">
          {{
            Object.entries(result.by_corruption_type)
              .map(([k, v]) => `${k}:${v}`)
              .join(" · ")
          }}
        </p>
      </article>
    </section>
  </div>
</template>

<style scoped>
.controls {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
  z-index: 6;
  max-width: min(24rem, calc(100% - 2rem));
}

.toggle {
  font-weight: var(--weight-semibold);
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-strong);
  color: var(--color-text);
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

.form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: var(--space-2);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-dim);
}

.field input {
  width: 6rem;
  background: var(--color-bg-0);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  color: var(--color-text);
}

.link {
  background: transparent;
  border: none;
  color: var(--color-accent);
  font-size: var(--text-xs);
  text-decoration: underline;
  text-underline-offset: 2px;
  padding: 0 0 0.4rem;
}

.err {
  margin: 0;
  color: var(--color-critical);
  font-size: var(--text-sm);
}

.result {
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-xs);
}
</style>
