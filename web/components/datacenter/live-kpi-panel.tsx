"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Locale } from "@/config/i18n";
import type { DashboardKPI, XhsLiveTotals } from "@/types/datacenter";

function toLocaleCount(locale: Locale, value: number) {
  return Math.max(0, Math.round(value)).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function parseMetricValue(raw: string | undefined) {
  if (!raw) {
    return 0;
  }
  const parsed = Number(raw.replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}

function AnimatedTotalValue({
  locale,
  value,
  tickToken
}: {
  locale: Locale;
  value: number;
  tickToken: number;
}) {
  const [display, setDisplay] = useState(value);
  const [rising, setRising] = useState(false);
  const [refreshed, setRefreshed] = useState(false);
  const previousRef = useRef(value);

  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = value;

    if (value <= previous) {
      setDisplay(value);
      setRising(false);
      return;
    }

    const distance = value - previous;
    const duration = 820;
    const startedAt = performance.now();
    setRising(true);
    let frameId = 0;

    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(previous + distance * eased);
      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      } else {
        setDisplay(value);
        window.setTimeout(() => setRising(false), 220);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [value]);

  useEffect(() => {
    if (tickToken <= 0) return;
    setRefreshed(true);
    const timer = window.setTimeout(() => setRefreshed(false), 260);
    return () => window.clearTimeout(timer);
  }, [tickToken]);

  return (
    <div
      className={`text-lg font-semibold tabular-nums transition-all duration-500 will-change-transform ${
        rising
          ? "text-[#ff7fa5] -translate-y-0.5 scale-[1.02] [text-shadow:0_0_18px_rgba(255,127,165,0.42)]"
          : refreshed
            ? "text-foreground/95 -translate-y-px scale-[1.015] [text-shadow:0_0_14px_rgba(255,176,136,0.25)]"
            : "text-foreground translate-y-0 scale-100"
      }`}
    >
      {toLocaleCount(locale, display)}
    </div>
  );
}

function buildFallbackTotals(fallbackKpis: DashboardKPI[]): XhsLiveTotals {
  return {
    notesTotal: parseMetricValue(fallbackKpis[0]?.value),
    creatorsTotal: parseMetricValue(fallbackKpis[1]?.value),
    commentsTotal: parseMetricValue(fallbackKpis[2]?.value),
    generatedAt: ""
  };
}

export function LiveKpiPanel({
  locale,
  initialTotals,
  fallbackKpis,
  pollMs = 5000
}: {
  locale: Locale;
  initialTotals: XhsLiveTotals | null;
  fallbackKpis: DashboardKPI[];
  pollMs?: number;
}) {
  const fallbackTotals = useMemo(() => buildFallbackTotals(fallbackKpis), [fallbackKpis]);
  const [totals, setTotals] = useState<XhsLiveTotals>(initialTotals ?? fallbackTotals);
  const [refreshTick, setRefreshTick] = useState(0);
  const fetchingRef = useRef(false);

  useEffect(() => {
    if (initialTotals) {
      setTotals(initialTotals);
    }
  }, [initialTotals]);

  useEffect(() => {
    async function refreshTotals() {
      if (document.hidden || fetchingRef.current) {
        return;
      }
      fetchingRef.current = true;
      try {
        const response = await fetch(`/api/dashboard/xhs/live-totals?t=${Date.now()}`, {
          cache: "no-store",
          signal: AbortSignal.timeout(Math.max(5000, pollMs + 2000))
        });
        if (!response.ok) {
          throw new Error("live totals api failed");
        }
        const payload = (await response.json()) as XhsLiveTotals;
        setTotals((previous) => {
          if (
            previous.notesTotal === payload.notesTotal &&
            previous.creatorsTotal === payload.creatorsTotal &&
            previous.commentsTotal === payload.commentsTotal &&
            previous.generatedAt === payload.generatedAt
          ) {
            return previous;
          }
          return payload;
        });
        setRefreshTick((value) => value + 1);
      } catch {
        // Keep previous values on transient failures.
      } finally {
        fetchingRef.current = false;
      }
    }

    function onVisibilityChange() {
      if (!document.hidden) {
        void refreshTotals();
      }
    }

    void refreshTotals();

    const timer = window.setInterval(() => {
      void refreshTotals();
    }, Math.max(1000, pollMs));
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [pollMs]);

  const cards = [
    {
      label: locale === "zh" ? "总笔记" : "Total Notes",
      value: totals.notesTotal
    },
    {
      label: locale === "zh" ? "总达人" : "Total Creators",
      value: totals.creatorsTotal
    },
    {
      label: locale === "zh" ? "总评论" : "Total Comments",
      value: totals.commentsTotal
    }
  ];

  return (
    <div className="rounded-2xl border border-border/30 bg-background/56 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-[0.2em] text-foreground/45">
        {locale === "zh" ? "总量快照" : "Totals Snapshot"}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        {cards.map((item) => (
          <div className="rounded-xl border border-border/25 bg-background/68 px-2.5 py-2" key={item.label}>
            <div className="text-[11px] text-foreground/52">{item.label}</div>
            <AnimatedTotalValue locale={locale} tickToken={refreshTick} value={item.value} />
          </div>
        ))}
      </div>
    </div>
  );
}
