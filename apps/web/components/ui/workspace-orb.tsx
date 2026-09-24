"use client";

import { useEffect, useState } from "react";
import FluidOrb from "./fluid-orb";

const themeColors: Record<string, string> = {
  light: "#3658bd",
  dark: "#83d6b5",
  green: "#19774b",
  blue: "#2867ba",
};

/** Theme-aware Rare UI Fluid Orb for ADDA accents. */
export default function WorkspaceOrb({ size = 180, className }: { size?: number; className?: string }) {
  const [color, setColor] = useState(themeColors.light);

  useEffect(() => {
    const read = () => {
      const theme = document.documentElement.dataset.theme || "light";
      setColor(themeColors[theme] || themeColors.light);
    };
    read();
    const observer = new MutationObserver(read);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return <FluidOrb size={size} color={color} className={className} aria-hidden="true" />;
}
