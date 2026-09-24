export type Provider = "demo" | "bedrock" | "extractive" | "tavily" | "local";
export type Agent = "auto" | "coding" | "document" | "search" | "research";
export type Health = { status: "ok"; provider: Provider; capabilities: Record<Exclude<Agent, "auto">, boolean>; limits?: Record<string, number> };
export type DocumentRef = { document_id: string; document_token: string; filename: string; pages: number; chunks: number };
export type ChatResponse = {
  request_id: string; agent: string; answer: string; provider: Provider;
  activity: { step: string; status: "completed"; detail: string; duration_ms: number }[];
  citations: { id?: string; title?: string; url?: string; page?: number; excerpt?: string }[];
  usage?: { provider: string; model: string; input_tokens?: number | null; output_tokens?: number | null; latency_ms: number; stop_reason?: string | null; truncated?: boolean; attempts?: number } | null;
};
const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); this.name = "ApiError"; } }
function requestSignal(timeoutMs: number, extra?: AbortSignal) {
  const timeout = AbortSignal.timeout(timeoutMs);
  return extra && typeof AbortSignal.any === "function" ? AbortSignal.any([timeout, extra]) : timeout;
}
async function request<T>(path: string, timeoutMs: number, init?: RequestInit, extra?: AbortSignal): Promise<T> {
  try {
    const response = await fetch(`${baseUrl}${path}`, { ...init, signal: requestSignal(timeoutMs, extra) });
    let payload;
    try { payload = JSON.parse(await response.text()); }
    catch (error) { if (!(error instanceof SyntaxError)) throw error; throw new Error(`The API returned an unexpected response (${response.status}). Please check the API address.`); }
    if (!response.ok) throw new ApiError(typeof payload?.detail?.message === "string" ? payload.detail.message : `The request could not be completed (${response.status}). Please try again.`, response.status);
    return payload as T;
  } catch (error) {
    if (extra?.aborted) throw error;
    if (error instanceof TypeError) throw new Error("Cannot reach the API. Check that the backend is running and allows this workspace address.");
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) throw new Error("The request timed out. Please try again.");
    throw error;
  }
}
const auth = (token: string): Record<string, string> => token ? { "X-Demo-Token": token } : {};
export const getHealth = () => request<Health>("/health", 5_000);
export const sendChat = (message: string, agent: Agent, token: string, document?: DocumentRef | null, signal?: AbortSignal) => request<ChatResponse>("/api/chat", 65_000, {
  method: "POST", headers: { "Content-Type": "application/json", ...auth(token), ...(document ? { "X-Document-Token": document.document_token } : {}) },
  body: JSON.stringify({ message, agent, ...(document ? { document_id: document.document_id } : {}) }),
}, signal);
export const uploadDocument = (file: File, token: string) => {
  const body = new FormData(); body.append("file", file);
  return request<DocumentRef>("/api/documents", 30_000, { method: "POST", headers: auth(token), body });
};
export const loadDemoDocument = (token: string) => request<DocumentRef>("/api/documents/demo", 15_000, { method: "POST", headers: auth(token) });
export const deleteDocument = async (document: DocumentRef, token: string) => {
  try {
    await request<{ deleted: boolean }>(`/api/documents/${encodeURIComponent(document.document_id)}`, 15_000, {
      method: "DELETE", headers: { ...auth(token), "X-Document-Token": document.document_token },
    });
  } catch (error) {
    // Expired or already removed documents require no further server cleanup.
    if (!(error instanceof ApiError && error.status === 404)) throw error;
  }
};
