"use client";

import { Suspense, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ThemePicker from "../../components/theme-picker";
import BrandMark from "../../components/brand-mark";
import WorkspaceOrb from "../../components/ui/workspace-orb";
import { useAuth } from "../../components/AuthProvider";

function VerifyEmailForm() {
  const { ready, user, configured, confirmSignUp, resendSignUp } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const email = useMemo(() => (params.get("email") || "").trim().toLowerCase(), [params]);
  const hintedTo = params.get("to") || "";
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [info, setInfo] = useState(
    email
      ? `We sent a verification code to ${hintedTo || email}.`
      : "Enter the email you registered with, then the verification code.",
  );
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [emailInput, setEmailInput] = useState(email);

  useEffect(() => {
    if (ready && user) router.replace("/");
  }, [ready, user, router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function verify(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    const target = (email || emailInput).trim().toLowerCase();
    if (!target) {
      setMessage("Enter the email address you registered with.");
      return;
    }
    if (!code.trim()) {
      setMessage("Enter the verification code from your email.");
      return;
    }
    setBusy(true);
    try {
      await confirmSignUp(target, code.trim());
      setInfo("Email verified. You can sign in now.");
      router.replace(`/login/?verified=1&email=${encodeURIComponent(target)}`);
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : "Verification failed.");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setMessage("");
    const target = (email || emailInput).trim().toLowerCase();
    if (!target) {
      setMessage("Enter your email before resending a code.");
      return;
    }
    setBusy(true);
    try {
      const delivery = await resendSignUp(target);
      setInfo(`We sent a new code to ${delivery.destination || target}.`);
      setCooldown(60);
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : "Could not resend the code.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready || user) return <div className="auth-loading" role="status">Loading…</div>;

  return <main className="auth-page">
    <section className="auth-story" aria-label="About ADDA AI">
      <div className="auth-story-top"><a className="brand" href="/login/" aria-label="ADDA AI home"><BrandMark />ADDA<span>AI</span></a><span className="auth-edition">MULTI-AGENT WORKSPACE</span></div>
      <div className="auth-story-content">
        <div className="auth-orb" aria-hidden="true"><WorkspaceOrb size={160} /></div>
        <span className="auth-kicker"><span /> VERIFY YOUR EMAIL</span>
        <h1>One more step.<br /><em>Then you are in.</em></h1>
        <p>We use a short code to confirm your email before opening the ADDA AI workspace.</p>
      </div>
      <p className="auth-story-foot">ADDA AI <span>·</span> Secure account access.</p>
    </section>
    <section className="auth-side" aria-label="Verify email">
      <div className="auth-top"><a href="/register/" className="auth-back">← Change email</a><ThemePicker /></div>
      <div className="auth-card">
        <div className="auth-mobile-brand"><BrandMark /><strong>ADDA AI</strong></div>
        <div className="auth-icon" aria-hidden="true">✉</div>
        <p className="auth-overline">CONFIRMATION</p>
        <h2>Verify your email</h2>
        <p className="auth-subtitle">{info}</p>
        <form onSubmit={(event) => void verify(event)} className="auth-form">
          {!email && (
            <label htmlFor="verify-email">Email
              <input id="verify-email" type="email" autoComplete="email" required value={emailInput} disabled={busy || !configured} onChange={(event) => { setEmailInput(event.target.value); setMessage(""); }} />
            </label>
          )}
          <label htmlFor="verify-code">Verification code
            <input id="verify-code" name="code" type="text" inputMode="numeric" autoComplete="one-time-code" placeholder="123456" required value={code} disabled={busy || !configured} onChange={(event) => { setCode(event.target.value); setMessage(""); }} />
          </label>
          {message && <p className="auth-message" role="alert">{message}</p>}
          <button className="auth-submit" type="submit" disabled={busy || !configured}>{busy ? "Verifying…" : "Verify"}<span>↗</span></button>
        </form>
        <p className="auth-switch">
          <button type="button" className="auth-link-btn" disabled={busy || cooldown > 0 || !configured} onClick={() => void resend()}>
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
          </button>
        </p>
        <p className="auth-switch">Already verified? <a href="/login/">Sign in</a></p>
      </div>
      <p className="auth-side-foot">Built for a transparent, evidence-led workflow.</p>
    </section>
  </main>;
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="auth-loading" role="status">Loading…</div>}>
      <VerifyEmailForm />
    </Suspense>
  );
}
