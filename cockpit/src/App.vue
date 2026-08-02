<script setup lang="ts">
import { onMounted, ref } from "vue";
import TwinViewport from "@/components/TwinViewport.vue";
import AssetDetailPanel from "@/components/AssetDetailPanel.vue";
import IncidentScrubber from "@/components/IncidentScrubber.vue";
import AskPrism from "@/components/AskPrism.vue";
import { setControlPlaneToken } from "@/api/controlPlane";
import { normalizeApiToken } from "@/lib/token";
import { useFleetStore } from "@/stores/fleet";
import { useIncidentStore } from "@/stores/incident";

const fleet = useFleetStore();
const incident = useIncidentStore();
const tokenInput = ref(localStorage.getItem("prism_cp_token") || "");
const showToken = ref(!tokenInput.value);

function saveToken() {
  const saved = setControlPlaneToken(tokenInput.value);
  tokenInput.value = saved;
  if (!saved) {
    fleet.error = "Token is empty after normalize — paste the hex from print_api_token.";
    showToken.value = true;
    return;
  }
  showToken.value = false;
  void refresh();
}

async function refresh() {
  await fleet.refresh();
  incident.rebuild();
}

onMounted(() => {
  const existing = normalizeApiToken(tokenInput.value);
  if (existing) {
    tokenInput.value = setControlPlaneToken(existing);
    void refresh();
  }
});
</script>

<template>
  <div class="shell">
    <header class="top">
      <div class="brand">
        <span class="mark" aria-hidden="true" />
        <div>
          <h1>PRISM</h1>
          <p class="tag">Fleet digital twin · control room</p>
        </div>
      </div>
      <div class="actions">
        <span v-if="fleet.authUser" class="mono auth-ok" aria-live="polite">
          auth: {{ fleet.authUser }}
        </span>
        <button type="button" @click="showToken = !showToken">API token</button>
        <button type="button" :disabled="fleet.loading" @click="refresh">
          {{ fleet.loading ? "Refreshing…" : "Refresh fleet" }}
        </button>
      </div>
    </header>

    <div v-if="showToken" class="token-bar" role="region" aria-label="Control-plane token">
      <label class="mono" for="tok">API token (viewer / inspector)</label>
      <input
        id="tok"
        v-model="tokenInput"
        class="mono"
        type="text"
        spellcheck="false"
        autocomplete="off"
        placeholder="docker compose exec -T control-plane python manage.py print_api_token"
        @keydown.enter="saveToken"
      />
      <button type="button" @click="saveToken">Use token</button>
    </div>

    <p v-if="fleet.error" class="banner err" role="alert">{{ fleet.error }}</p>

    <main class="main">
      <TwinViewport />
      <AssetDetailPanel />
      <AskPrism />
    </main>

    <IncidentScrubber />
  </div>
</template>

<style scoped>
.shell {
  height: 100%;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(ellipse at 20% 0%, #15202c 0%, transparent 55%),
    var(--color-bg-0);
}

.top {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-4);
  border-bottom: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-bg-1) 90%, transparent);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.mark {
  width: 0.85rem;
  height: 2rem;
  background: linear-gradient(180deg, var(--color-accent), var(--color-warn));
  border-radius: 2px;
}

h1 {
  font-size: var(--text-xl);
  letter-spacing: 0.12em;
}

.tag {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--color-text-dim);
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.auth-ok {
  font-size: var(--text-xs);
  color: var(--color-ok);
}

.token-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-2);
  border-bottom: 1px solid var(--color-border);
  font-size: var(--text-sm);
}

.token-bar input {
  flex: 1;
  min-width: 16rem;
  background: var(--color-bg-0);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
}

.banner {
  margin: 0;
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
}

.banner.err {
  background: color-mix(in srgb, var(--color-critical) 20%, var(--color-bg-1));
  color: var(--color-text);
}

.main {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}
</style>
