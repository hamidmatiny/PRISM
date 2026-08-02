/** W3C traceparent helpers — cockpit is the browser root of fleet→render traces. */

function hex(bytes: number): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Create a new root traceparent (`00-{traceId}-{spanId}-01`). */
export function newTraceparent(): string {
  return `00-${hex(16)}-${hex(8)}-01`;
}

/** Continue an existing trace with a new span id (same trace id). */
export function childTraceparent(parent: string): string {
  const parts = parent.split("-");
  if (parts.length !== 4 || parts[0] !== "00" || parts[1].length !== 32) {
    return newTraceparent();
  }
  return `00-${parts[1]}-${hex(8)}-${parts[3] || "01"}`;
}

let activeTrace: string | null = null;

/** Start (or replace) the active cockpit operation trace. */
export function beginOperationTrace(label = "cockpit.operation"): string {
  activeTrace = newTraceparent();
  if (typeof performance !== "undefined" && "mark" in performance) {
    performance.mark(label);
  }
  return activeTrace;
}

export function currentTraceparent(): string {
  if (!activeTrace) return beginOperationTrace();
  return childTraceparent(activeTrace);
}

/** Attach traceparent to fetch headers (mutates and returns the Headers). */
export function withTraceHeaders(headers: Headers): Headers {
  headers.set("traceparent", currentTraceparent());
  return headers;
}
