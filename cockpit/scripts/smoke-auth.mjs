#!/usr/bin/env node
/**
 * End-to-end auth smoke — same path the browser uses (Vite proxy + Bearer).
 *
 * Usage (repo root or cockpit/, with control-plane + `npm run dev` up):
 *   TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token) \
 *     node cockpit/scripts/smoke-auth.mjs
 */
const token = (process.env.TOKEN || "").trim();
const base = process.env.COCKPIT_PROXY || "http://127.0.0.1:9101/proxy/control";

if (!token || token.length < 32) {
  console.error("TOKEN env missing/short — use: manage.py print_api_token");
  process.exit(2);
}

async function get(path) {
  const res = await fetch(`${base}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await res.text();
  return { status: res.status, body };
}

const me = await get("/api/v1/me");
const wo = await get("/api/v1/work-orders");
const queue = await get("/api/v1/review-queue");

console.log("me", me.status, me.body.slice(0, 120));
console.log("work-orders", wo.status, wo.body.slice(0, 120));
console.log("review-queue", queue.status, `bytes=${queue.body.length}`);

if (me.status !== 200 || wo.status !== 200 || queue.status !== 200) {
  console.error("FAIL: expected 200 from me + work-orders + review-queue via proxy");
  process.exit(1);
}

const queueJson = JSON.parse(queue.body);
if (!Array.isArray(queueJson) || queueJson.length < 1) {
  console.error("FAIL: review-queue empty — twin/scrubber will have nothing to show");
  process.exit(1);
}

console.log("OK: auth works through cockpit proxy; queue has", queueJson.length, "findings");
