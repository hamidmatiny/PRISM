/**
 * Normalize a pasted control-plane token.
 * Accepts bare hex, "Bearer <hex>", or multi-line paste that includes Django
 * shell banners / bootstrap_rbac log lines — extracts the last hex token.
 */
export function normalizeApiToken(raw: string): string {
  const text = raw.replace(/^\uFEFF/, "").trim();
  if (!text) return "";

  const bearer = text.match(/^Bearer\s+(\S+)/i);
  if (bearer) return bearer[1].trim();

  // Prefer an explicit token=... from bootstrap_rbac log lines.
  const assigned = text.match(/token=([0-9a-fA-F]{32,64})/);
  if (assigned) return assigned[1];

  // Last hex run of token length (handles manage.py shell import banners).
  const hexRuns = text.match(/[0-9a-fA-F]{32,64}/g);
  if (hexRuns?.length) return hexRuns[hexRuns.length - 1];

  // Fallback: first line only (still better than sending a whole traceback).
  return text.split(/\r?\n/).map((l) => l.trim()).find(Boolean) || "";
}
