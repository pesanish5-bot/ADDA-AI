"use client";

import { useEffect, useState } from "react";
import FluidOrb from "./fluid-orb";

/** Theme-aware Rare UI Fluid Orb for ADDA accents. */
export default function WorkspaceOrb({ size = 180, className }: { size?: number; className?: string }) {
  const [color, setColor] = useState("#3658bd");

  useEffect(() => {
    const read = () => {
      const accent = getComputedStyle(document.documentElement).getPropertyValue("--teal").trim();
      setColor(/^#[0-9a-f]{6}$/i.test(accent) ? accent : "#3658bd");
    };
    read();
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-accent"] });
    return () => observer.disconnect();
  }, []);

  return <FluidOrb size={size} color={color} className={className} aria-hidden="true" />;
}
