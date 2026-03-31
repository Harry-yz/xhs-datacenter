"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { cn } from "@/utils/cn";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = resolvedTheme === "dark";

  return (
    <div className="inline-flex items-center rounded-full border border-border/35 bg-background/72 p-1 backdrop-blur-xl">
      <button
        aria-label="Switch to dark theme"
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-full transition duration-300",
          mounted && isDark ? "bg-foreground text-background" : "text-foreground/58 hover:text-foreground"
        )}
        onClick={() => setTheme("dark")}
        type="button"
      >
        <MoonStar className="h-3.5 w-3.5" />
      </button>
      <button
        aria-label="Switch to light theme"
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-full transition duration-300",
          mounted && !isDark ? "bg-foreground text-background" : "text-foreground/58 hover:text-foreground"
        )}
        onClick={() => setTheme("light")}
        type="button"
      >
        <SunMedium className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
