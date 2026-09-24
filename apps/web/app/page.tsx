"use client";
import { useEffect, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from "react";
import Markdown from "react-markdown";
import hljs from "highlight.js/lib/common";
import ThemePicker from "../components/theme-picker";
import WorkspaceOrb from "../components/ui/workspace-orb";
import BrandMark from "../components/brand-mark";
import { ApiError, getHealth, sendChat, uploadDocument, loadDemoDocument, deleteDocument, type Agent, type ChatResponse, type Health, type DocumentRef, type Provider } from "../lib/api";

const specialists = [
  { id: "coding", mark: "</>", name: "Coding", description: "Build, explain & debug" },
  { id: "document", mark: "▤", name: "Documents", description: "Answers with page evidence" },
  { id: "search", mark: "⌕", name: "Search", description: "Find sources on the web" },
  { id: "research", mark: "◇", name: "Research", description: "Follow the evidence" },
] as const;
const labels: Record<Provider, string> = { demo: "Fixed coding fixture · no model", bedrock: "Generated with Amazon Bedrock", extractive: "Retrieved document evidence · no model", tavily: "Retrieved web sources · Tavily", local: "Generated with local model" };
const agentLabels: Record<string, string> = { coding: "Coding Agent", document: "Document Agent", search: "Search Agent", research: "Research Agent" };
const tryPrompts = [
  { id: "coding", label: "Code a function", prompt: "Write a Python function to reverse a string.", hint: "Coding" },
  { id: "search", label: "Search the web", prompt: "What are the latest developments in AI agents?", hint: "Search", needs: "search" as const },
  { id: "document", label: "Explore sample PDF", prompt: "", hint: "Documents", needs: "document" as const, sample: true },
  { id: "research", label: "Research this file", prompt: "Research this document: summarize the evidence and identify the risks and limitations.", hint: "Research", needsDoc: true },
] as const;
function pendingSteps(agent: Agent): string[] {
  if (agent === "research") return ["Route request", "Research plan", "Collect evidence", "Assemble brief"];
  if (agent === "document") return ["Route request", "Retrieve passages", "Cite pages"];
  if (agent === "search") return ["Route request", "Query the web", "Rank sources"];
  if (agent === "coding") return ["Route request", "Generate coding answer"];
  return ["Choose specialist", "Run agent", "Return evidence"];
}
type Task = { prompt: string; response: ChatResponse };
const HISTORY_KEY = "adda.session.history";
function loadHistory(): Task[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Task[];
    return Array.isArray(parsed) ? parsed.filter((item) => item?.prompt && item?.response?.request_id).slice(0, 20) : [];
  } catch { return []; }
}
function saveHistory(items: Task[]) {
  try { sessionStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 20))); } catch { /* private mode / quota */ }
}
function safeUrl(url?: string) { return url && /^https?:\/\/./i.test(url) ? url : undefined; }
function hostOf(url?: string) {
  const href = safeUrl(url);
  if (!href) return undefined;
  try { return new URL(href).hostname.replace(/^www\./, ""); } catch { return undefined; }
}
function textOf(node: ReactNode): string { return typeof node === "string" ? node : Array.isArray(node) ? node.map(textOf).join("") : ""; }
function specialistStatus(id: Exclude<Agent, "auto">, available: boolean, health: Health | null) {
  if (!health) return "Offline";
  if (id === "coding") return health.provider === "demo" ? "Demo" : health.provider === "bedrock" ? "Configured" : "Ready";
  if (!available) return id === "search" ? "Key needed" : id === "research" ? "Add doc" : "Offline";
  return id === "search" ? "Live" : "Ready";
}
function statusClass(status: string) {
  if (status === "Demo") return "demo";
  if (status === "Live" || status === "Enabled") return "live";
  if (status === "Ready" || status === "Configured") return "ready";
  return "wait";
}
function Code({ children, className }: { children?: ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const code = textOf(children);
  const language = className?.replace("language-", "") || "text";
  const block = Boolean(className) || code.endsWith("\n");
  if (!block) return <code>{children}</code>;
  const highlighted = hljs.getLanguage(language) ? hljs.highlight(code, { language, ignoreIllegals: true }).value : null;
  return <div className="code-block"><div className="code-toolbar"><span>{language}</span><button type="button" onClick={async () => { try { await navigator.clipboard.writeText(code); setCopied(true); setCopyError(false); setTimeout(() => setCopied(false), 2000); } catch { setCopyError(true); } }}>{copyError ? "Select text to copy" : copied ? "Copied ✓" : "Copy code"}</button></div><pre>{highlighted ? <code dangerouslySetInnerHTML={{ __html: highlighted }} /> : <code>{code}</code>}</pre></div>;
}
function SourceCard({ item, index, fallback }: { item: ChatResponse["citations"][number]; index: number; fallback?: string }) {
  const href = safeUrl(item.url);
  const domain = hostOf(item.url);
  return <li className={href ? "web-source" : "doc-source"}>
    <div className="source-heading">
      <span className="source-id">{item.id || index + 1}</span>
      <div className="source-copy">
        <strong>{href ? <a href={href} target="_blank" rel="noopener noreferrer">{item.title || href}</a> : item.title || fallback || "Document source"}</strong>
        {domain && <span className="source-domain">{domain}</span>}
      </div>
      {item.page && <span className="page-tag">Page {item.page}</span>}
    </div>
    {item.excerpt && <details className="source-excerpt"><summary>View source excerpt</summary><blockquote>{item.excerpt}</blockquote></details>}
  </li>;
}
export default function Workspace() {
  const [health, setHealth] = useState<Health | null>(null);
  const [connection, setConnection] = useState("Connecting");
  const [message, setMessage] = useState("");
  const [agent, setAgent] = useState<Agent>("auto");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [document, setDocument] = useState<DocumentRef | null>(null);
  const [history, setHistory] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [submitted, setSubmitted] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [tokenOpen, setTokenOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const tokenInput = useRef<HTMLInputElement>(null);
  const runAbort = useRef<AbortController | null>(null);
  const historyReady = useRef(false);
  const result = selected?.response;
  const locked = busy || uploading;
  const ready = (id: Exclude<Agent, "auto">) => {
    if (id === "research") return Boolean(health?.capabilities.search) || Boolean(document && health?.capabilities.document);
    return Boolean(health?.capabilities[id]);
  };
  async function checkConnection() { setConnection("Connecting"); try { setHealth(await getHealth()); setConnection("Workspace connected"); } catch { setHealth(null); setConnection("Workspace offline"); } }
  function revealToken(focus = true) {
    setTokenOpen(true);
    if (focus) queueMicrotask(() => tokenInput.current?.focus());
  }
  useEffect(() => {
    const restored = loadHistory();
    if (restored.length) setHistory(restored);
    historyReady.current = true;
    void checkConnection();
    return () => { runAbort.current?.abort(); };
  }, []);
  useEffect(() => {
    if (!historyReady.current) return;
    saveHistory(history);
  }, [history]);
  function newTask() { setMessage(""); setAgent("auto"); setSelected(null); setError(""); setSubmitted(""); setMenuOpen(false); }
  function stopTask() {
    if (!busy) return;
    runAbort.current?.abort();
    runAbort.current = null;
    setBusy(false);
    setError("Task stopped. Your previous results are still in This Session.");
  }
  function goHome() {
    if (locked) return;
    newTask();
    if (typeof window !== "undefined" && window.location.pathname !== "/") window.location.assign("/");
  }
  function applyTry(item: (typeof tryPrompts)[number]) {
    if (locked) return;
    if ("sample" in item && item.sample) {
      void attach();
      return;
    }
    if ("needsDoc" in item && item.needsDoc && !document) {
      setError("Attach a PDF or TXT first, then run Research.");
      return;
    }
    setAgent(item.id as Agent);
    setMessage(item.prompt);
    setSelected(null);
    setError("");
    setMenuOpen(false);
  }
  function clearHistory() {
    if (locked || !history.length) return;
    setHistory([]);
    setSelected(null);
    saveHistory([]);
  }
  async function removeDocument() {
    if (locked || !document) return;
    setUploading(true); setUploadError("");
    try {
      await deleteDocument(document, token); setDocument(null);
      if (agent === "document" || agent === "research") setAgent("auto");
    } catch (failure) {
      setUploadError(`The document is still attached because cleanup failed. Try removing it again. ${failure instanceof Error ? failure.message : ""}`);
    } finally { setUploading(false); }
  }
  async function attach(file?: File) {
    if (locked) return;
    setUploading(true); setUploadError(""); setDragging(false);
    try {
      if (file && !/\.(pdf|txt)$/i.test(file.name)) throw new Error("Choose a text-based PDF or a UTF-8 TXT file.");
      if (file && file.size > 5 * 1024 * 1024) throw new Error("Choose a file smaller than 5 MB.");
      const doc = file ? await uploadDocument(file, token) : await loadDemoDocument(token);
      const previous = document;
      setDocument(doc); setAgent("auto"); setMessage("Summarize this document and cite the supporting pages."); setSelected(null); setError("");
      if (previous) {
        try { await deleteDocument(previous, token); }
        catch { setUploadError("Your new document is ready, but the previous document could not be removed from the API. It will expire automatically within one hour."); }
      }
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) revealToken();
      setUploadError(failure instanceof Error ? failure.message : "The document could not be uploaded.");
    }
    finally { setUploading(false); if (fileInput.current) fileInput.current.value = ""; }
  }
  async function run(event?: FormEvent) {
    event?.preventDefault(); if (locked || !message.trim()) return;
    const wantsDocument = /\b(pdf|document|uploaded|attachment|summarize|summary|cite|budget|pages?)\b/i.test(message)
      && !/\b(search|latest|news|web|today|current|recent)\b/i.test(message);
    if (agent === "auto" && wantsDocument && !document) {
      setError("Attach a PDF or TXT first. Auto-route uses the Document agent only when a file is attached.");
      return;
    }
    if (agent === "document" && !document) {
      setError("Attach a PDF or TXT before running the Document agent.");
      return;
    }
    runAbort.current?.abort();
    const controller = new AbortController();
    runAbort.current = controller;
    setBusy(true); setError(""); setSelected(null); setSubmitted(message.trim()); setMenuOpen(false);
    try {
      const response = await sendChat(message.trim(), agent, token, document, controller.signal);
      if (controller.signal.aborted) return;
      const task = { prompt: message.trim(), response };
      setSelected(task);
      setHistory((items) => [task, ...items].slice(0, 20));
    } catch (failure) {
      if (controller.signal.aborted) return;
      if (failure instanceof ApiError && failure.status === 401) revealToken();
      setError(failure instanceof Error ? failure.message : "Something went wrong. Please try again.");
    } finally {
      if (runAbort.current === controller) {
        runAbort.current = null;
        setBusy(false);
      }
    }
  }
  function onDrop(event: DragEvent) {
    event.preventDefault(); setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void attach(file);
  }
  const providerTitle = result ? labels[result.provider] || result.provider : health?.provider === "demo" ? "Coding uses an offline sample. Documents use real retrieval." : health?.provider === "bedrock" ? "Bedrock configured · model access verified by each response" : "Your task. The right capability. A visible trail of evidence.";
  const routeHint = agent === "auto" ? "Auto-route" : agentLabels[agent] || agent;
  return <div className={`workspace${menuOpen ? " nav-open" : ""}`} aria-busy={locked}>
    <div className="nav-scrim" onClick={() => setMenuOpen(false)} hidden={!menuOpen} />
    <aside className="sidebar">
      <div className="sidebar-top">
        <button type="button" className="brand" onClick={goHome} aria-label="ADDA AI home" disabled={locked}><BrandMark />ADDA<span>AI</span></button>
        <button className="menu-button" type="button" aria-expanded={menuOpen} aria-controls="workspace-nav" onClick={() => setMenuOpen((open) => !open)}>{menuOpen ? "Close" : "Menu"}</button>
      </div>
      <button className="new-task" onClick={newTask} disabled={locked}><span>＋</span> New task</button>
      <div className="workspace-label">Workspace</div>
      <button className={`nav-item ${agent === "auto" ? "selected" : ""}`} onClick={() => { setAgent("auto"); setMenuOpen(false); }} disabled={locked}><span>↗</span> Automatic routing</button>
      <div id="workspace-nav" className="sidebar-nav">
        <p className="sidebar-heading">SPECIALISTS</p>
        <nav aria-label="Specialist agents">{specialists.map((item) => {
          const available = ready(item.id);
          const status = specialistStatus(item.id, available, health);
          return <button key={item.id} className={`specialist agent-${item.id} ${agent === item.id ? "active" : ""}`} disabled={locked || !available} onClick={() => { setAgent(item.id); setMenuOpen(false); }}>
            <span className="agent-mark">{item.mark}</span>
            <span className="specialist-text"><strong>{item.name}</strong><small>{item.description}</small></span>
            <span className={`status-chip ${statusClass(status)}`}>{status}</span>
          </button>;
        })}</nav>
        <section className="task-history">
          <p className="sidebar-heading">THIS SESSION <span>{history.length}</span>{history.length > 0 && <button type="button" className="history-clear" disabled={locked} onClick={clearHistory}>Clear</button>}</p>
          {history.length ? history.map((task) => <button className={selected === task ? "history-item active" : "history-item"} key={task.response.request_id} disabled={locked} onClick={() => { setSelected(task); setError(""); setSubmitted(task.prompt); setMessage(task.prompt); setAgent(specialists.some((item) => item.id === task.response.agent) ? task.response.agent as Agent : "auto"); setMenuOpen(false); }}>
            <span>{task.prompt}</span>
            <small>{agentLabels[task.response.agent] || task.response.agent} · completed</small>
          </button>) : <p className="history-empty">Completed tasks stay in this browser tab.</p>}
        </section>
      </div>
      <div className="sidebar-bottom"><BrandMark className="session-avatar" title="ADDA AI" /><div><strong>Personal workspace</strong><p>Saved in this browser tab</p></div></div>
    </aside>
    <main>
      <header className="topbar">
        <span>Workspace <span className="crumb">/</span><strong>{result ? agentLabels[result.agent] || "Task result" : busy ? "Running" : "New task"}</strong></span>
        <div className="topbar-actions">
          <ThemePicker />
          <button className={`connection ${health ? "online" : ""}`} onClick={() => void checkConnection()} title="Refresh backend availability"><i />{connection}<span>↻</span></button>
        </div>
      </header>
      <div className={`content ${result || busy ? "has-result" : "empty-workspace"}`}>
        <div className={`intro ${result || busy ? "compact" : ""}`}>
          {!result && !busy && <div className="hero-orb" aria-hidden="true"><WorkspaceOrb size={220} /></div>}
          <div className="eyebrow">ADDA AI workspace</div>
          <h1>{result ? "Your task, completed." : busy ? "Working on your task" : "What are you working on?"}</h1>
          <p>Start with a question or a document. ADDA routes it to the right specialist.</p>
        </div>
        <div className="working-grid">
          <section className="task-area" aria-labelledby="task-heading">
            <form className={`composer${dragging ? " dragging" : ""}`} onSubmit={(event) => void run(event)} onDragOver={(event) => { event.preventDefault(); if (ready("document")) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              <div className="card-heading"><h2 id="task-heading">{result ? "Start another task" : "Your task"}</h2><span className="task-number">{routeHint}</span></div>
              <label className="sr-only" htmlFor="message">Your task</label>
              <textarea id="message" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask a question, describe a coding task, or explore a document…" maxLength={12000} disabled={locked} required />
              {document && <div className="attachment"><span className="attachment-icon">▤</span><div><strong>{document.filename}</strong><small>{document.pages} pages · {document.chunks} passages · ready for retrieval</small></div><button type="button" disabled={locked} onClick={() => void removeDocument()} aria-label="Remove attached document">×</button></div>}
              {dragging && <p className="drop-hint">Drop a PDF or TXT to attach it</p>}
              <div className="composer-bottom">
                <div className="composer-tools">
                  <label className="agent-select"><select aria-label="Agent routing" value={agent} onChange={(event) => setAgent(event.target.value as Agent)} disabled={locked}><option value="auto">Auto-route</option>{specialists.map((item) => <option key={item.id} value={item.id} disabled={!ready(item.id)}>{item.name}</option>)}</select></label>
                  <button className="upload-button" type="button" disabled={locked || !ready("document")} onClick={() => fileInput.current?.click()} title="Upload PDF or TXT">{uploading ? "Uploading…" : "＋ Attach"}</button>
                </div>
                <button className="run-button" disabled={locked || !message.trim()} type="submit">{busy ? "Working…" : "Run task"}<span>↗</span></button>
              </div>
            </form>
            <input ref={fileInput} className="sr-only" type="file" accept=".pdf,.txt" aria-label="Upload document" onChange={(event) => { const file = event.target.files?.[0]; if (file) void attach(file); }} />
            {!result && !busy && <div className="try-row" aria-label="Suggested tasks">
              <span>TRY THIS</span>
              {tryPrompts.map((item) => {
                const needsSearch = "needs" in item && item.needs === "search";
                const needsDocCap = "needs" in item && item.needs === "document";
                const needsDoc = "needsDoc" in item && item.needsDoc;
                const disabled = locked
                  || (needsSearch && !ready("search"))
                  || (needsDocCap && !ready("document"))
                  || (needsDoc && !document);
                return <button key={item.id} type="button" disabled={disabled} onClick={() => applyTry(item)}>
                  <em>{item.hint}</em>{item.label}
                </button>;
              })}
            </div>}
            <p className="attachment-help">PDF or TXT, up to 5 MB. Document access expires after one hour.</p>
            <div className="provider-note" role="status">{providerTitle}</div>
            {uploadError && <div className="error-box" role="alert"><strong>Document notice</strong><p>{uploadError}</p></div>}
            <details className="access-settings" open={tokenOpen} onToggle={(event) => setTokenOpen((event.target as HTMLDetailsElement).open)}><summary>Workspace access token</summary><label htmlFor="token">Only if this demo API is protected</label><input id="token" ref={tokenInput} type="password" autoComplete="off" value={token} disabled={locked} onChange={(event) => setToken(event.target.value)} placeholder="Enter the demo access token" /><small>Kept only in this tab’s memory. The public hosted demo does not need a token.</small></details>
            {busy && <div className="loading-box" role="status"><WorkspaceOrb size={56} className="loading-orb" /><div className="loading-copy"><strong>Running {routeHint}</strong><p>{submitted}</p><p>Completed steps appear when the API returns. Nothing is simulated.</p><button type="button" className="stop-button" onClick={stopTask}>Stop</button></div></div>}
            {error && <div className="error-box" role="alert"><strong>We couldn’t complete this task</strong><p>{error}</p><button type="button" disabled={locked} onClick={() => void run()}>Try again ↗</button></div>}
            {result && <article className={`result-card agent-${result.agent}`}>
              <div className="result-header"><span className="result-agent">ADDA → {agentLabels[result.agent] || result.agent}</span><span className="complete">✓ Complete</span></div>
              {result.activity.length > 0 && <ol className="workflow-path" aria-label="Completed route">{result.activity.map((item, index) => <li key={`${item.step}-${index}`}><span className="step-index">{index + 1}</span>{item.step.replaceAll("_", " ")}</li>)}</ol>}
              <p className="submitted"><span>You</span>{selected?.prompt}</p>
              <div className="markdown"><Markdown skipHtml components={{ pre: ({ children }) => <>{children}</>, code: ({ children, className }) => <Code className={className}>{children}</Code>, img: () => null, a: ({ children, href }) => safeUrl(href) ? <a href={safeUrl(href)} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span> }}>{result.answer}</Markdown></div>
              {result.citations.length > 0 && <section className="sources"><h3>{result.agent === "search" ? "Web sources" : result.agent === "research" ? "Research evidence" : "Retrieved passages"} <span>{result.citations.length}</span></h3><ul className="citations">{result.citations.map((item, index) => <SourceCard key={`${item.id || index}-${item.page || item.url || "src"}`} item={item} index={index} fallback={document?.filename} />)}</ul></section>}
              <div className="result-footer"><span>{labels[result.provider] || result.provider}</span><span>Request {result.request_id.slice(0, 8)}</span></div>
            </article>}
          </section>
          {(result || busy) && <aside className="activity-panel" aria-labelledby="activity-heading">
            <div className="activity-title"><h2 id="activity-heading">Agent activity</h2><span className="activity-count">{result?.activity.length || (busy ? "…" : "—")}</span></div>
            <p className="activity-subtitle">{busy ? "Expected path while the specialist works." : "Completed steps for this task"}</p>
            {result ? <ol className="trace">{result.activity.map((item, index) => <li key={`${item.step}-${index}`}><span className="trace-check">✓</span><div><strong>{item.step.replaceAll("_", " ")}</strong><p>{item.detail}</p><small>{item.duration_ms} ms · completed</small></div></li>)}</ol> : <ol className="trace pending-trace" aria-live="polite">{pendingSteps(agent).map((step, index) => <li key={step} className={index === 0 ? "active-step" : ""}><span className="trace-check">{index === 0 ? "…" : index + 1}</span><div><strong>{step}</strong><p>{index === 0 ? "In progress" : "Waiting"}</p></div></li>)}</ol>}
            <div className="trace-note">{result ? labels[result.provider] : busy ? <button type="button" className="stop-button" onClick={stopTask}>Stop task</button> : "Waiting for the response"}</div>
          </aside>}
        </div>
        <footer className="page-footer"><span>Each task is independent. History stays in this tab.</span><a href="/login/">Account preview</a></footer>
      </div>
    </main>
  </div>;
}
