"use client";

import { useState, type FormEvent } from "react";
import ThemePicker from "./theme-picker";
import WorkspaceOrb from "./ui/workspace-orb";
import BrandMark from "./brand-mark";

export default function AuthView({ mode }: { mode: "login" | "register" }) {
  const registering = mode === "register";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (registering && password !== confirm) {
      setMessage("Passwords do not match. Check both fields and try again.");
      return;
    }
    setMessage("Account sign-in is not connected yet. Your details were not sent or saved. You can explore the demo workspace now.");
  }

  return <main className="auth-page">
    <section className="auth-story" aria-label="About ADDA AI">
      <div className="auth-story-top"><a className="brand" href="/" aria-label="ADDA AI home"><BrandMark />ADDA<span>AI</span></a><span className="auth-edition">MULTI-AGENT WORKSPACE</span></div>
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
      <div className="auth-top"><a href="/" className="auth-back">← Back to workspace</a><ThemePicker /></div>
      <div className="auth-card">
        <div className="auth-mobile-brand"><BrandMark /><strong>ADDA AI</strong></div>
        <div className="auth-icon" aria-hidden="true">{registering ? "＋" : "↗"}</div>
        <p className="auth-overline">YOUR WORKSPACE</p>
        <h2>{registering ? "Create your account" : "Welcome back"}</h2>
        <p className="auth-subtitle">{registering ? "Set up your place to work with ADDA AI." : "Sign in to continue to your workspace."}</p>
        <div className="auth-preview-note" role="note"><strong>Account preview</strong><span>Authentication is being prepared. This form does not send or save credentials, and the workspace remains open for the demo.</span></div>
        <form onSubmit={submit} className="auth-form">
          {registering && <label htmlFor="auth-name">Full name<input id="auth-name" name="name" type="text" autoComplete="name" placeholder="Your name" required minLength={2} maxLength={80} onChange={() => setMessage("")} /></label>}
          <label htmlFor="auth-email">Email address<input id="auth-email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required onChange={() => setMessage("")} /></label>
          <label htmlFor="auth-password">Password<div className="auth-password"><input id="auth-password" name="password" type={showPassword ? "text" : "password"} autoComplete={registering ? "new-password" : "current-password"} placeholder={registering ? "At least 8 characters" : "Enter your password"} required minLength={registering ? 8 : undefined} value={password} onChange={(event) => { setPassword(event.target.value); setMessage(""); }} /><button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? "Hide" : "Show"}</button></div></label>
          {registering && <label htmlFor="auth-confirm">Confirm password<input id="auth-confirm" name="confirm" type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Enter password again" required value={confirm} onChange={(event) => { setConfirm(event.target.value); setMessage(""); }} /></label>}
          {message && <p className="auth-message" role="alert">{message}</p>}
          <button className="auth-submit" type="submit">{registering ? "Create account" : "Sign in"}<span>↗</span></button>
        </form>
        <p className="auth-switch">{registering ? "Already have an account?" : "New to ADDA AI?"} <a href={registering ? "/login/" : "/register/"}>{registering ? "Sign in" : "Create an account"}</a></p>
        <div className="auth-divider"><span>OR</span></div>
        <a className="auth-demo" href="/">Explore the demo workspace <span>→</span></a>
      </div>
      <p className="auth-side-foot">Built for a transparent, evidence-led workflow.</p>
    </section>
  </main>;
}
