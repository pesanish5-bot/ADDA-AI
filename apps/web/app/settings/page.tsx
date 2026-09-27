"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AuthGate from "../../components/AuthGate";
import BrandMark from "../../components/brand-mark";
import ThemePicker from "../../components/theme-picker";
import { useAuth } from "../../components/AuthProvider";
import {
  getBilling,
  getProfile,
  getUsage,
  openBillingPortal,
  startCheckout,
  type BillingSummary,
  type Profile,
  type UsageSummary,
} from "../../lib/api";

const sections = [
  ["account", "Account"],
  ["plan", "Plan & usage"],
  ["appearance", "Appearance"],
  ["personalization", "Personalization"],
  ["integrations", "Integrations"],
  ["privacy", "Data & privacy"],
  ["security", "Security"],
] as const;

function number(value: number | undefined) {
  return new Intl.NumberFormat().format(value || 0);
}

function money(amount: number, currency: string) {
  return new Intl.NumberFormat(undefined, {
    style: "currency", currency: currency.toUpperCase(), maximumFractionDigits: 2,
  }).format(amount / 100);
}

function date(value?: string | number | null) {
  if (!value) return "—";
  const parsed = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function SettingsPage() {
  return <AuthGate><Settings /></AuthGate>;
}

function Settings() {
  const { user, signOut } = useAuth();
  const [active, setActive] = useState("account");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      const [nextProfile, nextBilling, nextUsage] = await Promise.all([
        getProfile(), getBilling(), getUsage(),
      ]);
      setProfile(nextProfile); setBilling(nextBilling); setUsage(nextUsage); setError("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Settings could not be loaded.");
    }
  }

  useEffect(() => {
    const result = new URLSearchParams(window.location.search).get("billing");
    if (result === "success") setNotice("Checkout completed. Your plan updates after Stripe confirms payment.");
    if (result === "cancelled") setNotice("Checkout was cancelled. No plan change was made.");
    void load();
  }, []);

  async function redirect(action: "checkout" | "portal") {
    setWorking(true); setError("");
    try {
      const result = action === "checkout" ? await startCheckout() : await openBillingPortal();
      window.location.assign(result.url);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Billing could not be opened.");
      setWorking(false);
    }
  }

  async function handleSignOut() {
    await signOut();
    window.location.replace("/login/");
  }

  const limits = billing?.entitlements;
  return <div className="settings-shell">
    <aside className="settings-nav">
      <Link className="settings-brand" href="/"><BrandMark /><span>ADDA <b>AI</b></span></Link>
      <Link className="settings-back" href="/">← Back to workspace</Link>
      <p>SETTINGS</p>
      <nav aria-label="Settings categories">
        {sections.map(([id, label]) => <button key={id} className={active === id ? "active" : ""} onClick={() => { setActive(id); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{label}</button>)}
      </nav>
      <button className="settings-signout" onClick={() => void handleSignOut()}>Sign out</button>
    </aside>
    <main className="settings-main">
      <header><div><p>ADDA AI</p><h1>Settings</h1><span>Manage your account, plan and workspace preferences.</span></div><ThemePicker /></header>
      {notice && <div className="settings-notice" role="status">{notice}</div>}
      {error && <div className="settings-error" role="alert">{error}<button onClick={() => void load()}>Retry</button></div>}

      <section id="account" className="settings-section"><div className="settings-heading"><div><h2>Account</h2><p>Your identity and membership details.</p></div><span className="plan-pill">{billing?.plan === "pro" ? "Pro" : "Free"}</span></div>
        <div className="settings-card account-card"><div className="settings-avatar">{(profile?.display_name || user?.email || "A")[0].toUpperCase()}</div><div><strong>{profile?.display_name || user?.name || "ADDA AI member"}</strong><p>{profile?.email || user?.email}</p></div></div>
        <dl className="settings-facts"><div><dt>Member since</dt><dd>{date(profile?.created_at)}</dd></div><div><dt>Last login</dt><dd>{date(profile?.last_login_at)}</dd></div><div><dt>Login count</dt><dd>{number(profile?.login_count)}</dd></div><div><dt>Account status</dt><dd>{profile?.status || "active"}</dd></div></dl>
      </section>

      <section id="plan" className="settings-section"><div className="settings-heading"><div><h2>Plan & usage</h2><p>Subscription access comes only from verified Stripe events.</p></div></div>
        <div className="plan-grid">
          <article className={`plan-card ${billing?.plan === "free" ? "current" : ""}`}><small>FREE</small><h3>Essentials</h3><p>Core agents with protected daily and monthly limits.</p><ul><li>{number(billing?.plan === "free" ? limits?.daily_requests : 25)} model requests per day</li><li>{number(billing?.plan === "free" ? limits?.monthly_tokens : 500000)} model tokens per month</li><li>Private history and document tools</li></ul>{billing?.plan === "free" && <span className="current-plan">Current plan</span>}</article>
          <article className={`plan-card pro ${billing?.plan === "pro" ? "current" : ""}`}><small>PRO</small><h3>{billing?.pro_offer ? `${money(billing.pro_offer.amount, billing.pro_offer.currency)} / ${billing.pro_offer.interval}` : "Pro access"}</h3><p>Higher model allowances with billing managed securely by Stripe.</p><ul><li>{number(billing?.plan === "pro" ? limits?.daily_requests : 100)} model requests per day</li><li>{number(billing?.plan === "pro" ? limits?.monthly_tokens : 2000000)} model tokens per month</li><li>Invoices and self-service cancellation</li></ul>{billing?.plan === "pro" ? <span className="current-plan">Current plan</span> : <button disabled={working || !billing?.configured || !billing?.pro_offer} onClick={() => void redirect("checkout")}>{billing?.configured ? "Upgrade securely" : "Paid plans coming soon"}</button>}</article>
        </div>
        {billing?.status === "past_due" && <div className="billing-warning">Payment needs attention. Open billing to update your payment method.</div>}
        {billing?.has_customer && <button className="secondary-action" disabled={working} onClick={() => void redirect("portal")}>Manage billing, payment method or cancellation ↗</button>}
        <div className="usage-cards"><article><span>Today</span><strong>{number(usage?.daily.requests)} / {number(usage?.daily.request_limit)}</strong><p>model requests</p><progress max={usage?.daily.request_limit || 1} value={usage?.daily.requests || 0} /></article><article><span>This month</span><strong>{number(usage?.monthly.tokens)} / {number(usage?.monthly.token_limit)}</strong><p>model tokens</p><progress max={usage?.monthly.token_limit || 1} value={usage?.monthly.tokens || 0} /></article></div>
        {billing?.invoices.length ? <div className="invoice-list"><h3>Invoices</h3>{billing.invoices.map((invoice) => <a key={invoice.id} href={invoice.hosted_invoice_url || invoice.invoice_pdf || "#"} target="_blank" rel="noopener noreferrer"><span><strong>{invoice.number || "Invoice"}</strong><small>{date(invoice.created)} · {invoice.status}</small></span><b>{money(invoice.amount_due, invoice.currency)} ↗</b></a>)}</div> : <p className="empty-setting">No invoices yet.</p>}
      </section>

      <section id="appearance" className="settings-section"><div className="settings-heading"><div><h2>Appearance</h2><p>Adaptive, light and dark modes with your preferred accent.</p></div><ThemePicker /></div></section>
      <section id="personalization" className="settings-section"><div className="settings-heading"><div><h2>Personalization</h2><p>Custom instructions and response preferences will live here.</p></div><span className="roadmap-chip">Next</span></div></section>
      <section id="integrations" className="settings-section"><div className="settings-heading"><div><h2>Integrations</h2><p>GitHub, Drive and other connections will require explicit per-service permission.</p></div><span className="roadmap-chip">Planned</span></div></section>
      <section id="privacy" className="settings-section"><div className="settings-heading"><div><h2>Data & privacy</h2><p>Export, retention and account deletion controls are the next privacy milestone.</p></div><span className="roadmap-chip">Planned</span></div></section>
      <section id="security" className="settings-section"><div className="settings-heading"><div><h2>Security</h2><p>Recent authentication activity and session revocation will appear here.</p></div><span className="roadmap-chip">Planned</span></div></section>
      {profile?.is_admin && <section className="settings-section admin-entry"><div><h2>Administration</h2><p>Review accounts, subscription state, usage and authentication activity.</p></div><Link href="/admin/">Open admin console →</Link></section>}
    </main>
  </div>;
}
