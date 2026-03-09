"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

type ThemeMode = "light" | "dark";

function applyTheme(theme: ThemeMode) {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function ThemeToggle({ showLabel = false }: { showLabel?: boolean }) {
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme_mode");
    if (stored === "light" || stored === "dark") {
      setTheme(stored);
      applyTheme(stored);
    } else {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initial: ThemeMode = prefersDark ? "dark" : "light";
      setTheme(initial);
      applyTheme(initial);
      localStorage.setItem("theme_mode", initial);
    }
    setReady(true);
  }, []);

  const onToggle = () => {
    const next: ThemeMode = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
    localStorage.setItem("theme_mode", next);
  };

  if (!ready) {
    return (
      <Button
        variant="outline"
        size={showLabel ? "sm" : "icon"}
        aria-label="Toggle theme"
        className="border-border/70 bg-card/70 backdrop-blur"
        disabled
      >
        <Sun className="h-4 w-4" />
        {showLabel && <span className="ml-2">Theme</span>}
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size={showLabel ? "sm" : "icon"}
      onClick={onToggle}
      aria-label="Toggle theme"
      className="border-border/70 bg-card/70 backdrop-blur"
    >
      {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
      {showLabel && <span className="ml-2">Theme</span>}
    </Button>
  );
}
