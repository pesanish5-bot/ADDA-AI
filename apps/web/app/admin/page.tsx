"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGate from "../../components/AuthGate";
import BrandMark from "../../components/brand-mark";
import { getAdminOverview, getBillingReadiness, type AdminOverview, type BillingReadiness } from "../../lib/api";

function date(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function compact(value: number) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export default function AdminPage() {
  return <AuthGate><Admin /></AuthGate>;
}

function Admin() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [billing, setBilling] = useState<BillingReadiness | null>(null);
  const [error, setError] = useState("");
  async function load() {
    try { const [overview, readiness] = await Promise.all([getAdminOverview(), getBillingReadiness()]); setData(overview); setBilling(readiness); setError(""); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Admin data could not be loaded."); }
  }
  useEffect(() => { void load(); }, []);

  return <div className="admin-shell">
    <header className="admin-header"><Link className="settings-brand" href="/"><BrandMark /><span>ADDA <b>AI</b></span></Link><nav><Link href="/settings/">Settings</Link><Link href="/">Workspace</Link></nav></header>
    <main className="admin-main"><div className="admin-title"><div><p>PRIVATE OPERATIONS</p><h1>Admin console</h1><span>Account, subscription, usage and authentication visibility.</span></div><button onClick={() => void load()}>Refresh</button></div>
      {error && <div className="settings-error" role="alert">{error}</div>}
      {!data && !error && <div className="admin-loading">Loading protected account data…</div>}
      {data && <>
        <section className="admin-stats" aria-label="Platform summary"><article><span>Total users</span><strong>{data.summary.users}</strong></article><article><span>Active accounts</span><strong>{data.summary.active_users}</strong></article><article><span>Pro subscribers</span><strong>{data.summary.pro_users}</strong></article><article><span>Recorded logins</span><strong>{data.summary.logins}</strong></article></section>
        {billing && <section className="admin-panel billing-readiness"><div className="admin-panel-title"><div><h2>Billing readiness</h2><p>Sanitized deployment checks. Credentials and secret identifiers are never shown.</p></div><span className={`readiness-${billing.status}`}>{billing.status}</span></div><div className="readiness-checks">{billing.checks.map((check) => <div key={check.check}><i className={check.ok ? "ok" : "failed"} /><span>{check.check.replaceAll("_", " ")}</span><strong>{check.ok ? "Pass" : "Action needed"}</strong></div>)}</div></section>}
        <section className="admin-panel"><div className="admin-panel-title"><div><h2>Users</h2><p>No passwords, tokens, prompts or documents are exposed here.</p></div><span>{data.users.length}</span></div><div className="admin-table-wrap"><table><thead><tr><th>User</th><th>Status</th><th>Plan</th><th>Last login</th><th>Logins</th><th>Monthly usage</th></tr></thead><tbody>{data.users.map((user) => <tr key={user.id}><td><strong>{user.display_name || "Member"}</strong><small>{user.email}</small></td><td><span className={`admin-status ${user.status}`}>{user.status}</span></td><td><strong>{user.plan === "pro" ? "Pro" : "Free"}</strong><small>{user.subscription_status}</small></td><td>{date(user.last_login_at)}</td><td>{user.login_count}</td><td><strong>{user.monthly_requests} requests</strong><small>{compact(user.monthly_tokens)} tokens</small></td></tr>)}</tbody></table></div></section>
        <section className="admin-panel"><div className="admin-panel-title"><div><h2>Authentication activity</h2><p>Successful and rejected account events retained by the API.</p></div><span>{data.events.length}</span></div><div className="admin-events">{data.events.length ? data.events.map((event) => <article key={String(event.id)}><i className={event.success ? "ok" : "failed"} /><div><strong>{event.event_type.replaceAll("_", " ")}</strong><small>{event.user_id ? `User ${event.user_id.slice(0, 8)}…` : "Anonymous"}</small></div><time>{date(event.created_at)}</time></article>) : <p>No authentication events recorded yet.</p>}</div></section>
      </>}
    </main>
  </div>;
}
