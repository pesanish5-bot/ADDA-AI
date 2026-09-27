"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import ThemePicker from "../../components/theme-picker";
import BrandMark from "../../components/brand-mark";
import WorkspaceOrb from "../../components/ui/workspace-orb";
import { useAuth } from "../../components/AuthProvider";
import { PASSWORD_RULES } from "../../lib/cognito";

export default function ForgotPasswordPage() {
  const { ready, user, configured, forgotPassword, confirmForgotPassword } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<"email" | "reset">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (ready && user) router.replace("/");
  }, [ready, user, router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function sendCode(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setBusy(true);
    try {
      const delivery = await forgotPassword(email.trim().toLowerCase());
      setInfo(`If an account exists for that email, a reset code was sent${delivery.destination ? ` to ${delivery.destination}` : ""}.`);
      setStep("reset");
      setCooldown(60);
    } catch {
      // Avoid account enumeration: same UX on failure paths Cognito may still reveal.
      setInfo("If an account exists for that email, a reset code was sent.");
      setStep("reset");
      setCooldown(60);
    } finally {
      setBusy(false);
    }
  }

  async function reset(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    if (password !== confirm) {
      setMessage("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await confirmForgotPassword(email.trim().toLowerCase(), code.trim(), password);
      router.replace("/login/?reset=1");
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : "Could not reset password.");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setMessage("");
    setBusy(true);
    try {
      await forgotPassword(email.trim().toLowerCase());
      setInfo("If an account exists, a new reset code was sent.");
      setCooldown(60);
    } catch {
      setInfo("If an account exists, a new reset code was sent.");
      setCooldown(60);
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
        <span className="auth-kicker"><span /> ACCOUNT RECOVERY</span>
        <h1>Reset access.<br /><em>Keep working.</em></h1>
        <p>Use the code from your email to choose a new password for ADDA AI.</p>
      </div>
      <p className="auth-story-foot">ADDA AI <span>·</span> Secure account access.</p>
    </section>
    <section className="auth-side" aria-label="Forgot password">
      <div className="auth-top"><a href="/login/" className="auth-back">← Back to sign in</a><ThemePicker /></div>
      <div className="auth-card">
        <div className="auth-mobile-brand"><BrandMark /><strong>ADDA AI</strong></div>
        <div className="auth-icon" aria-hidden="true">↺</div>
        <p className="auth-overline">PASSWORD</p>
        <h2>{step === "email" ? "Forgot password" : "Choose a new password"}</h2>
        <p className="auth-subtitle">{step === "email" ? "Enter your account email. We will send a reset code if it exists." : info || "Enter the code and your new password."}</p>
        {step === "email" ? (
          <form onSubmit={(event) => void sendCode(event)} className="auth-form">
            <label htmlFor="forgot-email">Email
              <input id="forgot-email" type="email" autoComplete="email" required value={email} disabled={busy || !configured} onChange={(event) => setEmail(event.target.value)} />
            </label>
            {message && <p className="auth-message" role="alert">{message}</p>}
            <button className="auth-submit" type="submit" disabled={busy || !configured}>{busy ? "Sending…" : "Send reset code"}<span>↗</span></button>
          </form>
        ) : (
          <form onSubmit={(event) => void reset(event)} className="auth-form">
            <label htmlFor="reset-code">Reset code
              <input id="reset-code" type="text" inputMode="numeric" autoComplete="one-time-code" required value={code} disabled={busy} onChange={(event) => setCode(event.target.value)} />
            </label>
            <label htmlFor="reset-password">New password
              <div className="auth-password">
                <input id="reset-password" type={showPassword ? "text" : "password"} autoComplete="new-password" required minLength={PASSWORD_RULES.minLength} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
                <button type="button" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button>
              </div>
            </label>
            <label htmlFor="reset-confirm">Confirm password
              <input id="reset-confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" required value={confirm} disabled={busy} onChange={(event) => setConfirm(event.target.value)} />
            </label>
            <p className="auth-hint">{PASSWORD_RULES.label}</p>
            {message && <p className="auth-message" role="alert">{message}</p>}
            {info && <p className="auth-message ok" role="status">{info}</p>}
            <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Saving…" : "Reset password"}<span>↗</span></button>
          </form>
        )}
        {step === "reset" && (
          <p className="auth-switch">
            <button type="button" className="auth-link-btn" disabled={busy || cooldown > 0} onClick={() => void resend()}>
              {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
            </button>
          </p>
        )}
        <p className="auth-switch">Remembered it? <a href="/login/">Sign in</a></p>
      </div>
      <p className="auth-side-foot">Built for a transparent, evidence-led workflow.</p>
    </section>
  </main>;
}
