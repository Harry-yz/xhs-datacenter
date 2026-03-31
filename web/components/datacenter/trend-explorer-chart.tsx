"use client";

import { useEffect, useRef, useState } from "react";

import { type TrendExplorerVM, type TrendSeriesPoint, type TrendWindow } from "@/types/datacenter";

type NormalizedPoint = { x: number; y: number; raw: TrendSeriesPoint };
type TrendVariant = "default" | "ribbon" | "holo";

function normalizeSeries(items: TrendSeriesPoint[]) {
  if (!items.length) {
    return [] as NormalizedPoint[];
  }

  const max = Math.max(...items.map((item) => item.value));
  const min = Math.min(...items.map((item) => item.value));
  const range = Math.max(max - min, 1);

  return items.map((item, index) => {
    const x = (index / Math.max(items.length - 1, 1)) * 100;
    const y = 100 - ((item.value - min) / range) * 100;
    return { x, y, raw: item };
  });
}

function toSmoothPath(points: NormalizedPoint[]) {
  if (!points.length) {
    return "";
  }

  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`;
  }

  const tension = 0.9;
  let path = `M ${points[0].x} ${points[0].y}`;

  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[Math.max(index - 1, 0)];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[Math.min(index + 2, points.length - 1)];

    const cp1x = p1.x + (((p2.x - p0.x) / 6) * tension);
    const cp1y = p1.y + (((p2.y - p0.y) / 6) * tension);
    const cp2x = p2.x - (((p3.x - p1.x) / 6) * tension);
    const cp2y = p2.y - (((p3.y - p1.y) / 6) * tension);

    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }

  return path;
}

function toAreaPath(points: NormalizedPoint[], linePath: string) {
  if (!points.length || !linePath) {
    return "";
  }

  const firstX = points[0].x;
  const lastX = points[points.length - 1].x;
  return `${linePath} L ${lastX} 100 L ${firstX} 100 Z`;
}

export function TrendExplorerChart({
  data,
  title,
  subtitle,
  windowLabel,
  compact = false,
  variant = "default"
}: {
  data: TrendExplorerVM;
  title: string;
  subtitle?: string;
  windowLabel: Record<TrendWindow, string>;
  compact?: boolean;
  variant?: TrendVariant;
}) {
  const [windowSize, setWindowSize] = useState<TrendWindow>(data.defaultWindow);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [reduceMotion, setReduceMotion] = useState(false);
  const rafRef = useRef<number | null>(null);
  const pendingHoverRef = useRef<{ index: number; cursor: { x: number; y: number } } | null>(null);
  const isRibbon = variant === "ribbon";
  const isHolo = variant === "holo";
  const hasSubtitle = Boolean(subtitle?.trim());
  const items = data.windows[windowSize];
  const normalized = normalizeSeries(items);
  const linePath = toSmoothPath(normalized);
  const areaPath = toAreaPath(normalized, linePath);
  const activePoint = activeIndex === null ? null : normalized[activeIndex];
  const latest = items.at(-1)?.value ?? 0;
  const previous = items.at(-2)?.value ?? latest;
  const delta = previous === 0 ? 0 : ((latest - previous) / previous) * 100;
  const chartId = `trend-${data.metricKey}`;
  const firstLabel = items.at(0)?.date ?? "";
  const middleLabel = items.length ? items[Math.floor((items.length - 1) / 2)]?.date ?? "" : "";
  const lastLabel = items.at(-1)?.date ?? "";

  const visual = isHolo
    ? {
        surfaceStartAlpha: 0.085,
        surfaceEndAlpha: 0.02,
        areaStartAlpha: 0.13,
        areaEndAlpha: 0.03,
        lineStartAlpha: 0.95,
        lineEndAlpha: 0.94,
        lineGlowAlpha: 0.2,
        lineGlowWidth: 2.8,
        lineMainWidth: 1.1,
        sheenAlpha: 0.36,
        sheenWidth: 0.9,
        guideAlphaMid: 0.25,
        guideAlphaLow: 0.11,
        guideWidth: 0.22,
        guideGlowWidth: 0.72,
        guideGlowAlpha: 0.2,
        gridAlpha: 0.16,
        gridWidth: 0.22,
        glowBlur: 0.62,
        pointHaloRadius: 2.05,
        pointHaloAlpha: 0.16,
        pointRingRadius: 1.48,
        pointRingAlpha: 0.34,
        pointRingWidth: 0.16,
        pointOuterRingRadius: 1.9,
        pointOuterRingAlpha: 0.18,
        pointOuterRingWidth: 0.12,
        pointCoreRadius: 0.82,
        pointCoreStrokeAlpha: 0.76,
        pointCoreStrokeWidth: 0.2,
        cursorGlowActive: 0.78,
        cursorGlowIdle: 0.38,
        glowRadiusActive: 192,
        glowRadiusIdle: 170,
        glowWarmActive: 0.13,
        glowCoolActive: 0.05,
        glowWarmIdle: 0.035
      }
    : isRibbon
    ? {
        surfaceStartAlpha: 0.06,
        surfaceEndAlpha: 0.012,
        areaStartAlpha: 0.11,
        areaEndAlpha: 0.02,
        lineStartAlpha: 0.9,
        lineEndAlpha: 0.86,
        lineGlowAlpha: 0.14,
        lineGlowWidth: 2.05,
        lineMainWidth: 1.02,
        sheenAlpha: 0.32,
        sheenWidth: 0.62,
        guideAlphaMid: 0.19,
        guideAlphaLow: 0.08,
        guideWidth: 0.24,
        guideGlowWidth: 0.66,
        guideGlowAlpha: 0.16,
        gridAlpha: 0.13,
        gridWidth: 0.24,
        glowBlur: 0.54,
        pointHaloRadius: 1.82,
        pointHaloAlpha: 0.13,
        pointRingRadius: 1.32,
        pointRingAlpha: 0.3,
        pointRingWidth: 0.16,
        pointOuterRingRadius: 1.72,
        pointOuterRingAlpha: 0.14,
        pointOuterRingWidth: 0.1,
        pointCoreRadius: 0.76,
        pointCoreStrokeAlpha: 0.7,
        pointCoreStrokeWidth: 0.2,
        cursorGlowActive: 0.72,
        cursorGlowIdle: 0.34,
        glowRadiusActive: 170,
        glowRadiusIdle: 156,
        glowWarmActive: 0.1,
        glowCoolActive: 0.04,
        glowWarmIdle: 0.03
      }
    : {
        surfaceStartAlpha: 0.068,
        surfaceEndAlpha: 0.013,
        areaStartAlpha: 0.11,
        areaEndAlpha: 0.022,
        lineStartAlpha: 0.94,
        lineEndAlpha: 0.9,
        lineGlowAlpha: 0.16,
        lineGlowWidth: 2.1,
        lineMainWidth: 1.04,
        sheenAlpha: 0,
        sheenWidth: 0,
        guideAlphaMid: 0.2,
        guideAlphaLow: 0.09,
        guideWidth: 0.24,
        guideGlowWidth: 0.68,
        guideGlowAlpha: 0.17,
        gridAlpha: 0.14,
        gridWidth: 0.24,
        glowBlur: 0.56,
        pointHaloRadius: 1.9,
        pointHaloAlpha: 0.14,
        pointRingRadius: 1.42,
        pointRingAlpha: 0.34,
        pointRingWidth: 0.16,
        pointOuterRingRadius: 1.78,
        pointOuterRingAlpha: 0.15,
        pointOuterRingWidth: 0.1,
        pointCoreRadius: 0.78,
        pointCoreStrokeAlpha: 0.72,
        pointCoreStrokeWidth: 0.22,
        cursorGlowActive: 0.74,
        cursorGlowIdle: 0.36,
        glowRadiusActive: 176,
        glowRadiusIdle: 162,
        glowWarmActive: 0.1,
        glowCoolActive: 0.045,
        glowWarmIdle: 0.03
      };

  const pointTransition = reduceMotion
    ? "none"
    : "cx var(--trend-motion-fast) ease-out, cy var(--trend-motion-fast) ease-out, opacity var(--trend-motion-fast) ease-out";
  const guideTransition = reduceMotion
    ? "none"
    : "x1 var(--trend-motion-fast) ease-out, x2 var(--trend-motion-fast) ease-out, opacity var(--trend-motion-fast) ease-out";

  function clearHover() {
    pendingHoverRef.current = null;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setActiveIndex(null);
    setCursor(null);
  }

  function updateHoverAtPointer(target: SVGSVGElement, clientX: number, clientY: number) {
    if (!items.length) {
      setActiveIndex(null);
      setCursor(null);
      return;
    }

    const rect = target.getBoundingClientRect();
    const ratio = (clientX - rect.left) / rect.width;
    const yRatio = (clientY - rect.top) / rect.height;
    const safeX = Math.min(Math.max(ratio, 0), 1);
    const safeY = Math.min(Math.max(yRatio, 0), 1);
    const nextIndex = Math.round(safeX * (items.length - 1));
    const clamped = Math.min(Math.max(nextIndex, 0), items.length - 1);

    pendingHoverRef.current = {
      index: clamped,
      cursor: {
        x: safeX * 100,
        y: safeY * 100
      }
    };

    if (reduceMotion) {
      const hover = pendingHoverRef.current;
      if (hover) {
        setActiveIndex(hover.index);
        setCursor(hover.cursor);
      }
      return;
    }

    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        const hover = pendingHoverRef.current;
        if (hover) {
          setActiveIndex(hover.index);
          setCursor(hover.cursor);
        }
        rafRef.current = null;
      });
    }
  }

  useEffect(
    () => () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    },
    []
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handleChange = (event: MediaQueryListEvent) => {
      setReduceMotion(event.matches);
    };

    setReduceMotion(media.matches);
    media.addEventListener("change", handleChange);

    return () => {
      media.removeEventListener("change", handleChange);
    };
  }, []);

  return (
    <section className={`section-frame overflow-hidden ${compact ? "p-4 md:p-5" : ""}`}>
      <div className={`flex flex-wrap items-start justify-between ${compact ? "mb-3 gap-2.5" : "mb-4 gap-3"}`}>
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-foreground/45">{data.metricLabel}</p>
          <h3 className={`font-display tracking-tight text-foreground ${compact ? "mt-1 text-lg md:text-[1.3rem]" : "mt-1.5 text-xl md:text-[1.45rem]"}`}>{title}</h3>
          {hasSubtitle ? (
            <p className={`text-muted-foreground ${compact ? "mt-0.5 text-[11px] md:text-xs" : "mt-1 text-xs md:text-sm"}`}>{subtitle}</p>
          ) : null}
        </div>

        <div className={`flex items-center ${compact ? "gap-2" : "gap-2.5"}`}>
          <div className="flex rounded-full border border-border/30 bg-white/35 p-0.5 backdrop-blur-md">
            {([7, 30, 90] as const).map((item) => (
              <button
                className={`rounded-full transition ${
                  windowSize === item
                    ? "bg-peach-500 text-white shadow-sm"
                    : "text-foreground/62 hover:bg-white/70 hover:text-foreground"
                } ${compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"}`}
                key={item}
                onClick={() => {
                  setWindowSize(item);
                  clearHover();
                }}
                type="button"
              >
                {windowLabel[item]}
              </button>
            ))}
          </div>

          <div className={`rounded-2xl border border-border/35 bg-white/40 text-right backdrop-blur-md ${compact ? "px-2.5 py-1.5" : "px-3 py-1.5"}`}>
            <div className={`font-display tracking-tight text-foreground ${compact ? "text-lg md:text-2xl" : "text-lg md:text-xl"}`}>{latest.toLocaleString()}</div>
            <div className="text-[11px] text-peach-600">
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      <div
        className={`relative ${compact ? "h-[12.5rem] md:h-[13.75rem] lg:h-[14.25rem]" : "h-[16rem] md:h-[17rem] lg:h-[18rem]"}`}
        onPointerLeave={(event) => {
          if (event.pointerType !== "touch") {
            clearHover();
          }
        }}
      >
        {isHolo ? (
          <div
            aria-hidden
            className={`pointer-events-none absolute inset-0 z-[2] trend-matrix-overlay ${reduceMotion ? "" : "trend-matrix-overlay-active"}`}
          />
        ) : null}
        <div
          className="pointer-events-none absolute inset-0 z-[1] transition-opacity duration-200 ease-out"
          style={{
            background: cursor
              ? `radial-gradient(${visual.glowRadiusActive}px circle at ${cursor.x}% ${cursor.y}%, hsl(var(--trend-glow-warm) / ${visual.glowWarmActive}), hsl(var(--trend-glow-cool) / ${visual.glowCoolActive}) 36%, transparent 72%)`
              : `radial-gradient(${visual.glowRadiusIdle}px circle at 72% 32%, hsl(var(--trend-glow-warm) / ${visual.glowWarmIdle}), transparent 74%)`,
            opacity: cursor ? visual.cursorGlowActive : visual.cursorGlowIdle
          }}
        />
        <svg
          className="relative z-[2] h-full w-full"
          onPointerDown={(event) => {
            updateHoverAtPointer(event.currentTarget, event.clientX, event.clientY);
          }}
          onPointerMove={(event) => {
            updateHoverAtPointer(event.currentTarget, event.clientX, event.clientY);
          }}
          preserveAspectRatio="none"
          style={{ touchAction: "pan-y" }}
          viewBox="0 0 100 100"
        >
          <defs>
            <linearGradient id={`${chartId}-surface`} x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor={`hsl(var(--trend-surface-start) / ${visual.surfaceStartAlpha})`} />
              <stop offset="100%" stopColor={`hsl(var(--trend-surface-end) / ${visual.surfaceEndAlpha})`} />
            </linearGradient>
            <linearGradient id={`${chartId}-area`} x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor={`hsl(var(--trend-area-start) / ${visual.areaStartAlpha})`} />
              <stop offset="100%" stopColor={`hsl(var(--trend-area-end) / ${visual.areaEndAlpha})`} />
            </linearGradient>
            <linearGradient id={`${chartId}-line`} x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor={`hsl(var(--trend-line-start) / ${visual.lineStartAlpha})`} />
              <stop offset="100%" stopColor={`hsl(var(--trend-line-end) / ${visual.lineEndAlpha})`} />
            </linearGradient>
            <linearGradient id={`${chartId}-line-alt`} x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor={`hsl(var(--trend-line-start) / 0.25)`} />
              <stop offset="100%" stopColor={`hsl(var(--trend-line-end) / 0.58)`} />
            </linearGradient>
            <linearGradient id={`${chartId}-sheen`} x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor="hsl(var(--trend-point-stroke) / 0)" />
              <stop offset="48%" stopColor={`hsl(var(--trend-point-stroke) / ${visual.sheenAlpha})`} />
              <stop offset="100%" stopColor="hsl(var(--trend-point-stroke) / 0)" />
            </linearGradient>
            <linearGradient id={`${chartId}-guide`} x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="hsl(var(--trend-guide) / 0)" />
              <stop offset="30%" stopColor={`hsl(var(--trend-guide) / ${visual.guideAlphaMid})`} />
              <stop offset="70%" stopColor={`hsl(var(--trend-guide) / ${visual.guideAlphaLow})`} />
              <stop offset="100%" stopColor="hsl(var(--trend-guide) / 0)" />
            </linearGradient>
            <filter id={`${chartId}-glow`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur result="blur" stdDeviation={visual.glowBlur} />
            </filter>
          </defs>

          <rect fill={`url(#${chartId}-surface)`} height="100" width="100" x="0" y="0" />

          {[20, 40, 60, 80].map((y) => (
            <line
              key={y}
              stroke={`hsl(var(--trend-grid) / ${visual.gridAlpha})`}
              strokeDasharray="2 4"
              strokeWidth={visual.gridWidth}
              x1="0"
              x2="100"
              y1={y}
              y2={y}
            />
          ))}
          {[20, 40, 60, 80].map((x) => (
            <line
              key={`x-${x}`}
              stroke={`hsl(var(--trend-grid) / ${visual.gridAlpha})`}
              strokeDasharray="2 4"
              strokeWidth={visual.gridWidth}
              x1={x}
              x2={x}
              y1="0"
              y2="100"
            />
          ))}

          {areaPath ? <path d={areaPath} fill={`url(#${chartId}-area)`} /> : null}
          {linePath ? (
            <path
              d={linePath}
              fill="none"
              stroke={`url(#${chartId}-line)`}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeOpacity={visual.lineGlowAlpha}
              strokeWidth={visual.lineGlowWidth}
              filter={`url(#${chartId}-glow)`}
            />
          ) : null}
          {linePath ? (
            <path
              d={linePath}
              fill="none"
              stroke={`url(#${chartId}-line)`}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={visual.lineMainWidth}
            />
          ) : null}
          {linePath && isHolo ? (
            <path
              d={linePath}
              fill="none"
              stroke={`url(#${chartId}-line-alt)`}
              strokeDasharray="1.2 2.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={0.95}
            />
          ) : null}
          {linePath && isRibbon ? (
            <path
              d={linePath}
              fill="none"
              stroke={`url(#${chartId}-sheen)`}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={visual.sheenWidth}
            />
          ) : null}

          {activePoint ? (
            <>
              <line
                stroke={`url(#${chartId}-guide)`}
                strokeOpacity={visual.guideGlowAlpha}
                strokeWidth={visual.guideGlowWidth}
                x1={activePoint.x}
                x2={activePoint.x}
                y1="0"
                y2="100"
                style={{ transition: guideTransition }}
              />
              <line
                stroke={`url(#${chartId}-guide)`}
                strokeWidth={visual.guideWidth}
                x1={activePoint.x}
                x2={activePoint.x}
                y1="0"
                y2="100"
                style={{ transition: guideTransition }}
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                fill={`hsl(var(--trend-point-core) / ${visual.pointHaloAlpha})`}
                r={visual.pointHaloRadius}
                style={{ transition: pointTransition }}
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                fill="none"
                r={visual.pointRingRadius}
                stroke={`hsl(var(--trend-point-core) / ${visual.pointRingAlpha})`}
                strokeWidth={visual.pointRingWidth}
                style={{ transition: pointTransition }}
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                fill="none"
                r={visual.pointOuterRingRadius}
                stroke={`hsl(var(--trend-point-core) / ${visual.pointOuterRingAlpha})`}
                strokeWidth={visual.pointOuterRingWidth}
                style={{ transition: pointTransition }}
              />
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                fill="hsl(var(--trend-point-core) / 0.98)"
                r={visual.pointCoreRadius}
                stroke={`hsl(var(--trend-point-stroke) / ${visual.pointCoreStrokeAlpha})`}
                strokeWidth={visual.pointCoreStrokeWidth}
                style={{ transition: pointTransition }}
              />
            </>
          ) : null}
        </svg>

        {activePoint ? (
          <div
            className="trend-tooltip pointer-events-none absolute z-10 min-w-36 rounded-xl border border-slate-200/80 bg-white/92 px-3 py-2 text-xs shadow-sm backdrop-blur-md"
            style={{
              left: `${Math.max(8, Math.min(92, activePoint.x))}%`,
              top: `${Math.max(12, activePoint.y - 5)}%`,
              transform: "translate(-50%, -100%)"
            }}
          >
            <div className="text-slate-500">{activePoint.raw.date}</div>
            <div className="mt-1 font-medium tracking-tight text-slate-800">{activePoint.raw.value.toLocaleString()}</div>
          </div>
        ) : null}

        <div className="absolute inset-x-0 bottom-0 z-[3] flex justify-between text-[11px] text-foreground/46">
          <span>{firstLabel}</span>
          <span>{middleLabel}</span>
          <span>{lastLabel}</span>
        </div>
      </div>
    </section>
  );
}
