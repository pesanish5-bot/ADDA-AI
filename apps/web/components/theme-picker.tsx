"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const themes: Theme[] = ["light", "dark"];

export default function ThemePicker() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const saved = window.localStorage.getItem("adda-theme");
    if (themes.includes(saved as Theme)) {
      setTheme(saved as Theme);
      window.document.documentElement.dataset.theme = saved as Theme;
    } else if (saved) {
      // Clear stale theme values (e.g. previously saved "green" or "blue")
      window.localStorage.removeItem("adda-theme");
    }
  }, []);

  function changeTheme(next: Theme) {
    setTheme(next);
    window.document.documentElement.dataset.theme = next;
    window.localStorage.setItem("adda-theme", next);
  }

  return <label className="theme-control"><span>Theme</span><select aria-label="Theme" value={theme} onChange={(event) => changeTheme(event.target.value as Theme)}>{themes.map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>;
}
