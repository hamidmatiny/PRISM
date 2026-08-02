import { withTraceHeaders } from "@/lib/trace";

export interface AskResponse {
  answer: string;
  grounded: boolean;
  tools_used: string[];
  tool_calls: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  redactions: string[];
  error: string | null;
}

const BASE = import.meta.env.VITE_COPILOT_URL || "/proxy/copilot";

export async function askPrism(
  question: string,
  controlPlaneToken: string,
): Promise<AskResponse> {
  const headers = withTraceHeaders(new Headers({ "content-type": "application/json" }));
  const res = await fetch(`${BASE}/v1/ask`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      question,
      control_plane_token: controlPlaneToken || undefined,
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`ai-copilot /v1/ask: ${res.status} ${body}`);
  }
  return res.json() as Promise<AskResponse>;
}
