import { defineStore } from "pinia";
import { ref } from "vue";
import { acknowledgeIncident, journalTail, listBreakers, listIncidents, resolveIncident } from "@/api/incidentEngine";
import type { Breaker, Incident, JournalEntry } from "@/api/types";

/** Live view of incident-engine (Phase 14/15) — the Breaker Board's data source. */
export const useIncidentEngineStore = defineStore("incidentEngine", () => {
  const breakers = ref<Breaker[]>([]);
  const incidents = ref<Incident[]>([]);
  const journal = ref<JournalEntry[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastRefresh = ref<string | null>(null);
  const available = ref(true);

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      const [b, i, j] = await Promise.all([
        listBreakers(),
        listIncidents(),
        journalTail(200),
      ]);
      breakers.value = b;
      incidents.value = i;
      journal.value = j;
      error.value = null;
      available.value = true;
      lastRefresh.value = new Date().toISOString();
    } catch (e) {
      // incident-engine being unreachable degrades the board, never crashes the cockpit
      // (same fail-open posture incident-engine itself uses toward ingestion/cv-service).
      available.value = false;
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  async function acknowledge(incidentId: string): Promise<void> {
    await acknowledgeIncident(incidentId);
    await refresh();
  }

  async function resolve(incidentId: string): Promise<void> {
    await resolveIncident(incidentId);
    await refresh();
  }

  function openCount(): number {
    return breakers.value.filter((b) => b.state === "open").length;
  }

  function halfOpenCount(): number {
    return breakers.value.filter((b) => b.state === "half_open").length;
  }

  return {
    breakers,
    incidents,
    journal,
    loading,
    error,
    available,
    lastRefresh,
    refresh,
    acknowledge,
    resolve,
    openCount,
    halfOpenCount,
  };
});
