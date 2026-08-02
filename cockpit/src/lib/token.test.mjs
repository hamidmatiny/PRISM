/**
 * Tiny node:test suite for token normalize (no Vue tooling required).
 * Run: node --test src/lib/token.test.mjs  (from cockpit/)
 *
 * Mirrors normalizeApiToken in token.ts — keep in sync.
 */
import test from "node:test";
import assert from "node:assert/strict";

function normalizeApiToken(raw) {
  const text = raw.replace(/^\uFEFF/, "").trim();
  if (!text) return "";
  const bearer = text.match(/^Bearer\s+(\S+)/i);
  if (bearer) return bearer[1].trim();
  const assigned = text.match(/token=([0-9a-fA-F]{32,64})/);
  if (assigned) return assigned[1];
  const hexRuns = text.match(/[0-9a-fA-F]{32,64}/g);
  if (hexRuns?.length) return hexRuns[hexRuns.length - 1];
  return text.split(/\r?\n/).map((l) => l.trim()).find(Boolean) || "";
}

const HEX = "11d561b7c19321f8a6b114ebd9b810ba051b495400b59635";

test("bare hex", () => {
  assert.equal(normalizeApiToken(HEX), HEX);
});

test("Bearer prefix", () => {
  assert.equal(normalizeApiToken(`Bearer ${HEX}`), HEX);
});

test("manage.py shell banner pollution", () => {
  const polluted =
    "17 objects imported automatically (use -v 2 for details).\n\n" + HEX;
  assert.equal(normalizeApiToken(polluted), HEX);
});

test("bootstrap_rbac log line", () => {
  assert.equal(
    normalizeApiToken(`viewer: role=viewer token=${HEX} created=False`),
    HEX,
  );
});

test("empty", () => {
  assert.equal(normalizeApiToken("   "), "");
});
