import { getIdToken } from "./cognito";

export type Provider = "demo" | "bedrock" | "extractive" | "tavily" | "local";
export type Agent = "auto" | "coding" | "document" | "search" | "research";
export type Health = {
  status: "ok";
  provider: Provider;
  capabilities: Record<Exclude<Agent, "auto">, boolean>;
  limits?: Record<string, number>;
  auth?: { configured: boolean; provider: string; required: boolean };
};
export type DocumentRef = { document_id: string; document_token: string; filename: string; pages: number; chunks: number };
export type ChatResponse = {
  request_id: string; agent: string; answer: string; provider: Provider;
  activity: { step: string; status: "completed"; detail: string; duration_ms: number }[];
  citations: { id?: string; title?: string; url?: string; page?: number; excerpt?: string }[];
};
const baseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); this.name = "ApiError"; } }
function requestSignal(timeoutMs: number, extra?: AbortSignal) {
  const timeout = AbortSignal.timeout(timeoutMs);
  return extra && typeof AbortSignal.any === "function" ? AbortSignal.any([timeout, extra]) : timeout;
}
async function authHeaders(): Promise<Record<string, string>> {
  const token = await getIdToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
async function request<T>(path: string, timeoutMs: number, init?: RequestInit, extra?: AbortSignal): Promise<T> {
  try {
    const headers = {
      ...(init?.headers || {}),
      ...(await authHeaders()),
    };
    const response = await fetch(`${baseUrl}${path}`, { ...init, headers, signal: requestSignal(timeoutMs, extra) });
    let payload;
    try { payload = JSON.parse(await response.text()); }
    catch (error) { if (!(error instanceof SyntaxError)) throw error; throw new Error(`The API returned an unexpected response (${response.status}). Please check the API address.`); }
    if (!response.ok) {
      if (response.status === 401) throw new ApiError("Sign in required.", 401);
      throw new ApiError(typeof payload?.detail?.message === "string" ? payload.detail.message : `The request could not be completed (${response.status}). Please try again.`, response.status);
    }
    return payload as T;
  } catch (error) {
    if (extra?.aborted) throw error;
    if (error instanceof TypeError) throw new Error("Cannot reach the API. Check that the backend is running and allows this workspace address.");
    if (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name)) throw new Error("The request timed out. Please try again.");
    throw error;
  }
}
export const getHealth = () => request<Health>("/health", 5_000);
export const sendChat = (message: string, agent: Agent, document?: DocumentRef | null, signal?: AbortSignal) => request<ChatResponse>("/api/chat", 65_000, {
  method: "POST", headers: { "Content-Type": "application/json", ...(document ? { "X-Document-Token": document.document_token } : {}) },
  body: JSON.stringify({ message, agent, ...(document ? { document_id: document.document_id } : {}) }),
}, signal);
export const uploadDocument = (file: File) => {
  const body = new FormData(); body.append("file", file);
  return request<DocumentRef>("/api/documents", 30_000, { method: "POST", body });
};
export const loadDemoDocument = () => request<DocumentRef>("/api/documents/demo", 15_000, { method: "POST" });
export const deleteDocument = async (document: DocumentRef) => {
  try {
    await request<{ deleted: boolean }>(`/api/documents/${encodeURIComponent(document.document_id)}`, 15_000, {
      method: "DELETE", headers: { "X-Document-Token": document.document_token },
    });
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) throw error;
  }
};
