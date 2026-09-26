"use client";

import { useEffect, useId, useRef, useState, type CSSProperties } from "react";

type AppearanceMode = "adaptive" | "light" | "dark";
type ResolvedTheme = "light" | "dark";
type Accent = "ocean" | "forest" | "violet" | "amber" | "graphite";
type AppearancePreference = { mode: AppearanceMode; accent: Accent };

const STORAGE_KEY = "adda-appearance";
const LEGACY_KEY = "adda-theme";
const modes: { id: Exclude<AppearanceMode, "adaptive">; label: string; icon: string }[] = [
  { id: "light", label: "Light", icon: "☀" },
  { id: "dark", label: "Dark", icon: "◐" },
];
const accents: { id: Accent; label: string; color: string }[] = [
  { id: "ocean", label: "Ocean", color: "#4361ee" },
  { id: "forest", label: "Forest", color: "#27845e" },
  { id: "violet", label: "Violet", color: "#7657cf" },
  { id: "amber", label: "Amber", color: "#b26a0b" },
  { id: "graphite", label: "Graphite", color: "#596273" },
];
const validModes: AppearanceMode[] = ["adaptive", "light", "dark"];
const validAccents: Accent[] = ["ocean", "forest", "violet", "amber", "graphite"];
const fallback: AppearancePreference = { mode: "adaptive", accent: "ocean" };

function readPreference(): AppearancePreference {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Partial<AppearancePreference>;
      if (validModes.includes(saved.mode as AppearanceMode) && validAccents.includes(saved.accent as Accent)) {
        return { mode: saved.mode as AppearanceMode, accent: saved.accent as Accent };
      }
    }
    const legacy = window.localStorage.getItem(LEGACY_KEY);
    if (legacy === "light" || legacy === "dark") return { mode: legacy, accent: "ocean" };
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }
  return fallback;
}

function resolvedTheme(mode: AppearanceMode): ResolvedTheme {
  if (mode === "light" || mode === "dark") return mode;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function ThemePicker() {
  const [preference, setPreference] = useState<AppearancePreference | null>(null);
  const [resolved, setResolved] = useState<ResolvedTheme>("light");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const current = preference ?? fallback;

  useEffect(() => setPreference(readPreference()), []);

  useEffect(() => {
    if (!preference) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const next = resolvedTheme(preference.mode);
      setResolved(next);
      document.documentElement.dataset.theme = next;
      document.documentElement.dataset.appearance = preference.mode;
      document.documentElement.dataset.accent = preference.accent;
    };
    apply();
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preference));
      window.localStorage.removeItem(LEGACY_KEY);
    } catch {
      // The appearance still works for this page when persistence is unavailable.
    }
    if (preference.mode === "adaptive") media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);

  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const accentName = accents.find((item) => item.id === current.accent)?.label ?? "Ocean";
  const modeName = current.mode === "adaptive" ? "Adaptive" : current.mode === "dark" ? "Dark" : "Light";

  return (
    <div className="appearance-control" ref={rootRef}>
      <button type="button" className="appearance-trigger" aria-label={`Appearance: ${modeName}, ${accentName}`} aria-haspopup="dialog" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((visible) => !visible)}>
        <span className="appearance-trigger-icon" aria-hidden="true">{current.mode === "adaptive" ? "✦" : resolved === "dark" ? "◐" : "☀"}</span>
        <span className="appearance-trigger-copy"><strong>{modeName}</strong><small>{resolved === "dark" ? "Dark" : "Light"} · {accentName}</small></span>
        <span className="appearance-chevron" aria-hidden="true">⌄</span>
      </button>

      {open && (
        <div className="appearance-panel" id={panelId} role="dialog" aria-label="Appearance settings">
          <div className="appearance-panel-heading"><div><strong>Appearance</strong><p>Make the workspace feel like yours.</p></div><button type="button" onClick={() => setOpen(false)} aria-label="Close appearance settings">×</button></div>

          <button type="button" className={`adaptive-option${current.mode === "adaptive" ? " selected" : ""}`} aria-pressed={current.mode === "adaptive"} onClick={() => setPreference({ ...current, mode: current.mode === "adaptive" ? resolved : "adaptive" })}>
            <span className="adaptive-icon" aria-hidden="true">✦</span>
            <span><strong>Adaptive appearance</strong><small>Follow this device automatically</small></span>
            <span className="appearance-switch" aria-hidden="true"><i /></span>
          </button>

          <fieldset className="appearance-section">
            <legend>Mode</legend>
            <div className="mode-options">
              {modes.map((item) => <button key={item.id} type="button" className={current.mode === item.id ? "selected" : ""} aria-pressed={current.mode === item.id} onClick={() => setPreference({ ...current, mode: item.id })}><span aria-hidden="true">{item.icon}</span>{item.label}<i aria-hidden="true">✓</i></button>)}
            </div>
          </fieldset>

          <fieldset className="appearance-section accent-section">
            <legend>Accent</legend>
            <div className="accent-options">
              {accents.map((item) => <button key={item.id} type="button" className={current.accent === item.id ? "selected" : ""} aria-label={`${item.label} accent${current.accent === item.id ? ", selected" : ""}`} aria-pressed={current.accent === item.id} onClick={() => setPreference({ ...current, accent: item.id })} style={{ "--swatch": item.color } as CSSProperties}><span aria-hidden="true" /><small>{item.label}</small></button>)}
            </div>
          </fieldset>

          <p className="appearance-foot"><span aria-hidden="true">✓</span> Saved on this device</p>
        </div>
      )}
    </div>
  );
}
