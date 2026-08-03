#!/usr/bin/env node
/**
 * Capture real cockpit screenshots for docs/screenshots/.
 *
 *   VIEWER_TOKEN=… node cockpit/scripts/capture-demo-screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(ROOT, "docs/screenshots");
const BASE = process.env.PRISM_COCKPIT_URL || "http://127.0.0.1:9101";
const TOKEN = (process.env.VIEWER_TOKEN || process.env.TOKEN || "").trim();

if (!TOKEN) {
  console.error("VIEWER_TOKEN required");
  process.exit(1);
}

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
});

await page.goto(BASE, { waitUntil: "networkidle", timeout: 90_000 });

const tokenInput = page.locator("#tok");
await tokenInput.waitFor({ state: "visible", timeout: 45_000 });
await tokenInput.fill(TOKEN);
await page.getByRole("button", { name: "Use token" }).click();
await page.waitForTimeout(3500);

await page.screenshot({
  path: path.join(OUT, "cockpit-fleet-twin.png"),
  fullPage: false,
});

// Click canvas center to select a nearby asset when possible.
const canvas = page.locator("canvas").first();
if (await canvas.count()) {
  const box = await canvas.boundingBox();
  if (box) {
    await page.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.45);
    await page.waitForTimeout(1500);
  }
}

await page.screenshot({
  path: path.join(OUT, "cockpit-asset-detail.png"),
  fullPage: false,
});

await page.getByRole("button", { name: /ask prism/i }).click();
await page.waitForTimeout(500);
const askBox = page.locator("#ask-q");
await askBox.waitFor({ state: "visible", timeout: 15_000 });
await askBox.fill("How many open work orders and pending CV findings are there?");
await page.locator('form.form button[type="submit"]').click();
await page.waitForTimeout(3500);

await page.screenshot({
  path: path.join(OUT, "cockpit-ask-prism.png"),
  fullPage: false,
});

// Phase 15 -- Breaker Board: room-legible per-asset circuit-breaker state.
const breakerToggle = page.getByRole("button", { name: /breaker board/i });
if (await breakerToggle.count()) {
  await breakerToggle.click();
  await page.waitForTimeout(1500);
  await page.screenshot({
    path: path.join(OUT, "cockpit-breaker-board.png"),
    fullPage: false,
  });
}

// Phase 15 -- Scenario controls: admin-triggered seeded batch through real ingestion.
const scenarioToggle = page.getByRole("button", { name: /scenario controls/i });
if (await scenarioToggle.count()) {
  await scenarioToggle.click();
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(OUT, "cockpit-scenario-controls.png"),
    fullPage: false,
  });
}

await writeFile(
  path.join(OUT, "README.md"),
  `# Cockpit screenshots (Phase 11)

Captured from a live local stack (\`make demo\`) on ${new Date().toISOString()}.

| File | View |
|------|------|
| \`cockpit-fleet-twin.png\` | Digital twin fleet floor |
| \`cockpit-asset-detail.png\` | After canvas interaction / detail context |
| \`cockpit-ask-prism.png\` | Ask PRISM panel |
| \`cockpit-breaker-board.png\` | Breaker Board (Phase 15) |
| \`cockpit-scenario-controls.png\` | Scenario controls (Phase 15) |

Re-capture:

\`\`\`bash
make demo
cd cockpit && npm install -D playwright && npx playwright install chromium
VIEWER_TOKEN=$(docker compose exec -T control-plane python manage.py print_api_token viewer | tail -n1) \\
  node scripts/capture-demo-screenshots.mjs
\`\`\`
`,
  "utf8",
);

await browser.close();
console.log(`wrote screenshots under ${OUT}`);
