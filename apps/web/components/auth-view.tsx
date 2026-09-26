"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import ThemePicker from "./theme-picker";
import WorkspaceOrb from "./ui/workspace-orb";
import BrandMark from "./brand-mark";
import { useAuth } from "./AuthProvider";
import { PASSWORD_RULES } from "../lib/cognito";

export default function AuthView({ mode }: { mode: "login" | "register" }) {
  const registering = mode === "register";
  const { ready, configured, googleEnabled, user, signIn, signUp, signInWithGoogle } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && user) router.replace("/");
  }, [ready, user, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");

    if (!configured) {
      setMessage("Cognito is not configured. Add user pool and client IDs to .env.local, then restart.");
      return;
    }

    if (registering && password !== confirm) {
      setMessage("Passwords do not match. Check both fields and try again.");
      return;
    }

    setBusy(true);
    try {
      const normalized = email.trim().toLowerCase();
      if (registering) {
        const result = await signUp(name.trim(), normalized, password);
        if (result.status === "verify") {
          const params = new URLSearchParams({ email: normalized });
          if (result.destination) params.set("to", result.destination);
          router.replace(`/verify-email/?${params.toString()}`);
          return;
        }
        router.replace("/");
      } else {
        await signIn(normalized, password);
        router.replace("/");
      }
    } catch (failure) {
      const text = failure instanceof Error ? failure.message : "Something went wrong.";
      if (!registering && text.toLowerCase().includes("confirm your email")) {
        router.replace(`/verify-email/?email=${encodeURIComponent(email.trim().toLowerCase())}`);
        return;
      }
      setMessage(text);
    } finally {
      setBusy(false);
    }
  }

  async function onGoogle() {
    setMessage("");
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch (failure) {
      setMessage(failure instanceof Error ? failure.message : "Google sign-in failed.");
      setBusy(false);
    }
  }

  if (!ready || user) {
    return <div className="auth-loading" role="status">Loading…</div>;
  }

  return <main className="auth-page">
    <section className="auth-story" aria-label="About ADDA AI">
      <div className="auth-story-top"><a className="brand" href="/login/" aria-label="ADDA AI home"><BrandMark />ADDA<span>AI</span></a><span className="auth-edition">MULTI-AGENT WORKSPACE</span></div>
      <div className="auth-story-content">
        <div className="auth-orb" aria-hidden="true"><WorkspaceOrb size={160} /></div>
        <span className="auth-kicker"><span /> ONE PLACE FOR EVERY KIND OF WORK</span>
        <h1>One question.<br /><em>The right specialist.</em></h1>
        <p>Bring code, documents, and research into one workspace. See which agent handled your task and the evidence behind its answer.</p>
        <div className="auth-route" aria-label="How ADDA AI works">
          <div><span>01</span><strong>Ask or attach</strong><small>Start with a task or a document.</small></div>
          <div><span>02</span><strong>Route to an agent</strong><small>Coding, Search, Documents, or Research.</small></div>
          <div><span>03</span><strong>Inspect the result</strong><small>Follow the activity and sources.</small></div>
        </div>
      </div>
      <p className="auth-story-foot">ADDA AI <span>·</span> Different agents, one workspace.</p>
    </section>

    <section className="auth-side" aria-label={registering ? "Registration" : "Sign in"}>
      <div className="auth-top"><span className="auth-back-spacer" /><ThemePicker /></div>
      <div className="auth-card">
        <div className="auth-mobile-brand"><BrandMark /><strong>ADDA AI</strong></div>
        <div className="auth-icon" aria-hidden="true">{registering ? "＋" : "↗"}</div>
        <p className="auth-overline">YOUR WORKSPACE</p>
        <h2>{registering ? "Create your account" : "Welcome back"}</h2>
        <p className="auth-subtitle">{registering ? "Set up your place to work with ADDA AI." : "Sign in to continue to your workspace."}</p>

        {googleEnabled && (
          <button type="button" className="auth-google" onClick={() => void onGoogle()} disabled={busy || !configured}>
            <GoogleMark /> Continue with Google
          </button>
        )}
        {googleEnabled && <div className="auth-divider"><span>OR</span></div>}

        <form onSubmit={(event) => void submit(event)} className="auth-form">
          {registering && (
            <label htmlFor="auth-name">Full name
              <input id="auth-name" name="name" type="text" autoComplete="name" placeholder="Your name" required minLength={2} maxLength={80} value={name} disabled={busy || !configured} onChange={(event) => { setName(event.target.value); setMessage(""); }} />
            </label>
          )}
          <label htmlFor="auth-email">Email
            <input id="auth-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required value={email} disabled={busy || !configured} onChange={(event) => { setEmail(event.target.value); setMessage(""); }} />
          </label>
          <label htmlFor="auth-password">Password
            <div className="auth-password">
              <input id="auth-password" name="password" type={showPassword ? "text" : "password"} autoComplete={registering ? "new-password" : "current-password"} placeholder={registering ? "Create a password" : "Enter your password"} required minLength={registering ? PASSWORD_RULES.minLength : undefined} value={password} disabled={busy || !configured} onChange={(event) => { setPassword(event.target.value); setMessage(""); }} />
              <button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button>
            </div>
          </label>
          {registering && (
            <>
              <label htmlFor="auth-confirm">Confirm password
                <input id="auth-confirm" name="confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Enter password again" required value={confirm} disabled={busy || !configured} onChange={(event) => { setConfirm(event.target.value); setMessage(""); }} />
              </label>
              <p className="auth-hint">{PASSWORD_RULES.label}</p>
            </>
          )}
          {!registering && (
            <p className="auth-forgot"><a href="/forgot-password/">Forgot password?</a></p>
          )}
          {message && <p className="auth-message" role="alert">{message}</p>}
          <button className="auth-submit" type="submit" disabled={busy || !configured}>
            {busy ? "Working…" : registering ? "Create account" : "Sign in"}
            <span>↗</span>
          </button>
        </form>
        <p className="auth-switch">{registering ? "Already have an account?" : "Don't have an account?"} <a href={registering ? "/login/" : "/register/"}>{registering ? "Sign in" : "Create account"}</a></p>
        {!configured && (
          <p className="auth-message" role="status">Add Cognito pool and client IDs to <code>.env.local</code>, then restart the web app.</p>
        )}
      </div>
      <p className="auth-side-foot">Built for a transparent, evidence-led workflow.</p>
    </section>
  </main>;
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34.2 6.1 29.4 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.5-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7 12.9 19.6C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34.2 6.1 29.4 4 24 4 16.3 4 9.6 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 10-2 13.6-5.2l-6.3-5.2C29.3 35.3 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.5l.1.1 6.3 5.2C39.2 37.1 44 32 44 24c0-1.3-.1-2.5-.4-3.5z" />
    </svg>
  );
}
