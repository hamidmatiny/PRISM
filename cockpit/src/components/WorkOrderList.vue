<script setup lang="ts">
import type { WorkOrder } from "@/api/types";

defineProps<{ orders: WorkOrder[] }>();
</script>

<template>
  <section aria-label="Work order history">
    <header>
      <h3>Work orders</h3>
      <span class="mono muted">GET /api/v1/work-orders</span>
    </header>
    <p v-if="!orders.length" class="muted">No work orders for this asset.</p>
    <ul v-else>
      <li v-for="w in orders" :key="w.work_order_id">
        <div class="row">
          <span class="status" :data-status="w.status">{{ w.status }}</span>
          <strong>{{ w.title }}</strong>
        </div>
        <div class="mono meta">{{ w.work_order_id }} · {{ w.created_at }}</div>
        <p v-if="w.description" class="desc">{{ w.description }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
header {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
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

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.status {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  padding: 0.1rem 0.4rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  text-transform: uppercase;
}

.status[data-status="open"],
.status[data-status="in_progress"] {
  color: var(--color-warn);
  border-color: var(--color-warn);
}

.status[data-status="closed"] {
  color: var(--color-ok);
  border-color: var(--color-ok);
}

.meta {
  font-size: var(--text-xs);
  color: var(--color-text-dim);
  margin-top: var(--space-1);
}

.desc {
  margin: var(--space-2) 0 0;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
</style>
