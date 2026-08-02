<script setup lang="ts">
import { ref } from "vue";
import { askPrism, type AskResponse } from "@/api/copilot";

const open = ref(false);
const question = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const result = ref<AskResponse | null>(null);

const examples = [
  "What are the ping_count values from warehouse telemetry?",
  "How many CV findings are pending review?",
  "How many open work orders are there?",
  "What is the ping_count for PRISM-AST-001?",
];

function token(): string {
  return localStorage.getItem("prism_cp_token") || "";
}

async function ask(q?: string) {
  const text = (q ?? question.value).trim();
  if (!text) return;
  question.value = text;
  loading.value = true;
  error.value = null;
  result.value = null;
  try {
    result.value = await askPrism(text, token());
    if (result.value.error && !result.value.answer) {
      error.value = result.value.error;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="ask" :data-open="open">
    <button type="button" class="toggle" :aria-expanded="open" @click="open = !open">
      Ask PRISM
    </button>

    <section v-if="open" class="panel" aria-label="Ask PRISM copilot">
      <header>
        <h2>Ask PRISM</h2>
        <p class="muted">
          Tool-grounded answers only (activation-gateway, CV findings, work orders).
          Numbers must come from this turn’s tool calls — ADR-004.
        </p>
      </header>

      <form class="form" @submit.prevent="ask()">
        <label class="sr" for="ask-q">Question</label>
        <input
          id="ask-q"
          v-model="question"
          class="mono"
          type="text"
          autocomplete="off"
          placeholder="e.g. How many CV findings are pending?"
        />
        <button type="submit" :disabled="loading || !question.trim()">
          {{ loading ? "Asking…" : "Ask" }}
        </button>
      </form>

      <ul class="examples">
        <li v-for="ex in examples" :key="ex">
          <button type="button" class="link" @click="ask(ex)">{{ ex }}</button>
        </li>
      </ul>

      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <article v-if="result" class="answer">
        <p class="body">{{ result.answer }}</p>
        <p class="meta mono">
          grounded={{ result.grounded }} · tools={{ result.tools_used.join(", ") }}
          <span v-if="result.redactions.length"> · redacted={{ result.redactions.join(",") }}</span>
        </p>
        <details v-if="result.tool_calls.length">
          <summary>Tool calls ({{ result.tool_calls.length }})</summary>
          <pre class="mono">{{ JSON.stringify(result.tool_calls, null, 2) }}</pre>
        </details>
        <details v-if="result.evidence.length">
          <summary>Evidence ({{ result.evidence.length }})</summary>
          <pre class="mono">{{ JSON.stringify(result.evidence, null, 2) }}</pre>
        </details>
      </article>
    </section>
  </div>
</template>

<style scoped>
.ask {
  position: absolute;
  left: var(--space-4);
  bottom: calc(var(--scrubber-height) + var(--space-4));
  z-index: 6;
  max-width: min(28rem, calc(100% - 2rem));
}

.toggle {
  font-weight: var(--weight-semibold);
  background: var(--color-accent);
  color: #041016;
  border: none;
}

.toggle:hover {
  filter: brightness(1.05);
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
  max-height: min(70vh, 32rem);
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

.form {
  display: flex;
  gap: var(--space-2);
}

.form input {
  flex: 1;
  background: var(--color-bg-0);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  color: var(--color-text);
}

.examples {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.link {
  background: transparent;
  border: none;
  color: var(--color-accent);
  font-size: var(--text-xs);
  text-align: left;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.err {
  margin: 0;
  color: var(--color-critical);
  font-size: var(--text-sm);
}

.answer .body {
  margin: 0;
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.meta {
  margin: var(--space-2) 0 0;
  font-size: var(--text-xs);
  color: var(--color-text-dim);
}

details {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
}

pre {
  margin: var(--space-2) 0 0;
  padding: var(--space-2);
  background: var(--color-bg-0);
  border-radius: var(--radius-sm);
  overflow: auto;
  max-height: 10rem;
  font-size: 0.7rem;
}

.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
