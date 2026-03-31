"use client";

import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import type { ComposeOption, EChartsType } from "echarts/core";
import * as echarts from "echarts/core";
import type { LineSeriesOption } from "echarts/charts";
import { LineChart } from "echarts/charts";
import type { GridComponentOption, TooltipComponentOption } from "echarts/components";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useTheme } from "next-themes";
import { twMerge } from "tailwind-merge";

import type { TrendSeriesPoint } from "@/types/datacenter";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

type WindowSize = 7 | 30 | 90;
type Locale = "zh" | "en";
type TrendDatum = {
  date: string;
  newCount: number;
};

type TrendInput = Record<WindowSize, TrendSeriesPoint[]>;

type ECOption = ComposeOption<GridComponentOption | TooltipComponentOption | LineSeriesOption>;

const WINDOW_OPTIONS: WindowSize[] = [7, 30, 90];
const ANCHOR_DATE = new Date(Date.UTC(2026, 2, 25));

const COPY = {
  zh: {
    newNotes: "每日新增笔记",
    windows: {
      7: "7天",
      30: "30天",
      90: "90天"
    }
  },
  en: {
    newNotes: "Daily New Notes",
    windows: {
      7: "7D",
      30: "30D",
      90: "90D"
    }
  }
} as const;

function toIsoDate(value: Date) {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, "0");
  const day = String(value.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildWindowData(
  days: number,
  config: {
    base: number;
    rise: number;
    amplitude: number;
    minimum: number;
  }
) {
  const newCounts = Array.from({ length: days }, (_, index) => {
    const progress = index / Math.max(days - 1, 1);
    const seasonal =
      Math.sin((index + 1) * 0.57) * config.amplitude +
      Math.cos((index + 1) * 0.21) * config.amplitude * 0.52;
    return Math.max(config.minimum, Math.round(config.base + progress * config.rise + seasonal));
  });

  return newCounts.map((newCount, index) => {
    const currentDate = new Date(ANCHOR_DATE);
    currentDate.setUTCDate(ANCHOR_DATE.getUTCDate() - (days - 1 - index));

    return {
      date: toIsoDate(currentDate),
      newCount
    };
  });
}

const MOCK_DATA: Record<WindowSize, TrendDatum[]> = {
  7: buildWindowData(7, {
    base: 254,
    rise: 118,
    amplitude: 42,
    minimum: 180
  }),
  30: buildWindowData(30, {
    base: 198,
    rise: 144,
    amplitude: 56,
    minimum: 132
  }),
  90: buildWindowData(90, {
    base: 96,
    rise: 178,
    amplitude: 48,
    minimum: 68
  })
};

function formatNumber(locale: Locale, value: number) {
  return new Intl.NumberFormat(locale === "zh" ? "zh-CN" : "en-US").format(value);
}

function formatDate(locale: Locale, value: string) {
  const date = new Date(`${value}T00:00:00Z`);

  return new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en-US", {
    month: "short",
    day: "numeric"
  }).format(date);
}

function buildTooltipHtml({
  locale,
  date,
  newCount,
  isDark
}: {
  locale: Locale;
  date: string;
  newCount: number;
  isDark: boolean;
}) {
  const textColor = isDark ? "#f8fafc" : "#0f172a";
  const mutedTextColor = isDark ? "rgba(226,232,240,0.68)" : "#64748b";
  const borderColor = isDark ? "rgba(255,255,255,0.08)" : "#e2e8f0";
  const background = isDark ? "rgba(15,23,42,0.9)" : "rgba(255,255,255,0.92)";

  return `
    <div style="
      min-width: 160px;
      border-radius: 12px;
      border: 1px solid ${borderColor};
      background: ${background};
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      box-shadow: 0 10px 24px rgba(15, 23, 42, ${isDark ? 0.22 : 0.08});
      padding: 10px 12px;
      color: ${textColor};
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
    ">
      <div style="font-size:12px; line-height:16px; color:${mutedTextColor}; margin-bottom:8px;">
        ${formatDate(locale, date)}
      </div>
      <div style="display:flex; align-items:center; justify-content:space-between; gap:14px;">
        <div style="display:flex; align-items:center; gap:8px; color:${textColor}; font-size:13px;">
          <span style="width:8px; height:8px; border-radius:999px; background:#FF8AA8; box-shadow:0 0 0 6px rgba(255,138,168,0.14);"></span>
          <span>${COPY[locale].newNotes}</span>
        </div>
        <div style="font-size:14px; font-weight:700; font-variant-numeric: tabular-nums; text-align:right; color:${textColor};">
          ${formatNumber(locale, newCount)}
        </div>
      </div>
    </div>
  `;
}

export function PureTrendChart({
  locale = "zh",
  className,
  defaultWindow = 30,
  data
}: {
  locale?: Locale;
  className?: string;
  defaultWindow?: WindowSize;
  data?: TrendInput;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<EChartsType | null>(null);
  const { resolvedTheme } = useTheme();
  const [windowSize, setWindowSize] = useState<WindowSize>(defaultWindow);
  const [reduceMotion, setReduceMotion] = useState(false);
  const isDark = resolvedTheme === "dark";

  const dataset = useMemo(() => {
    const externalWindow = data?.[windowSize];
    if (!externalWindow || externalWindow.length === 0) {
      return MOCK_DATA[windowSize];
    }

    return externalWindow.map((item) => ({
      date: item.date,
      newCount: Math.max(0, Number(item.value ?? 0))
    }));
  }, [data, windowSize]);

  const option = useMemo<ECOption>(() => {
    const axisPointerColor = isDark ? "rgba(226,232,240,0.2)" : "rgba(148,163,184,0.72)";

    return {
      animation: !reduceMotion,
      animationDuration: reduceMotion ? 0 : 170,
      animationDurationUpdate: reduceMotion ? 0 : 120,
      animationEasing: "cubicOut",
      animationEasingUpdate: "cubicOut",
      grid: {
        left: 8,
        right: 8,
        top: 12,
        bottom: 10,
        containLabel: false
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: dataset.map((item) => item.date),
        show: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false }
      },
      yAxis: {
        type: "value",
        show: false,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        splitLine: { show: false }
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "transparent",
        borderWidth: 0,
        padding: 0,
        transitionDuration: reduceMotion ? 0 : 0.08,
        extraCssText: "box-shadow:none;",
        axisPointer: {
          type: "line",
          snap: true,
          lineStyle: {
            color: axisPointerColor,
            width: 1,
            type: "dashed"
          }
        },
        formatter: (params) => {
          const seriesParams = Array.isArray(params) ? params : [params];
          const datum = seriesParams[0] as { axisValue?: string; data?: number } | undefined;
          const date = String(datum?.axisValue ?? dataset.at(-1)?.date ?? "");
          const newCount = Number(datum?.data ?? dataset.at(-1)?.newCount ?? 0);

          return buildTooltipHtml({
            locale,
            date,
            newCount,
            isDark
          });
        },
        position: (point, _params, _dom, _rect, size) => {
          const [x, y] = point as number[];
          const [viewWidth, viewHeight] = size.viewSize;
          const [contentWidth, contentHeight] = size.contentSize;
          let left = x + 16;

          if (left + contentWidth > viewWidth - 8) {
            left = x - contentWidth - 16;
          }

          const top = Math.max(8, Math.min(y - contentHeight / 2, viewHeight - contentHeight - 8));
          return [left, top];
        }
      },
      series: [
        {
          name: COPY[locale].newNotes,
          type: "line",
          smooth: true,
          showSymbol: false,
          symbol: "circle",
          symbolSize: 7,
          data: dataset.map((item) => item.newCount),
          lineStyle: {
            width: 2,
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: "#FFDDC1" },
              { offset: 1, color: "#FF7FA5" }
            ])
          },
          itemStyle: {
            color: "#FF8AA8",
            borderColor: isDark ? "rgba(15,23,42,0.96)" : "#ffffff",
            borderWidth: 1.2,
            shadowBlur: 10,
            shadowColor: isDark ? "rgba(255,138,168,0.2)" : "rgba(255,138,168,0.16)"
          },
          emphasis: {
            scale: false,
            itemStyle: {
              color: "#FF8AA8",
              borderColor: isDark ? "rgba(15,23,42,0.96)" : "#ffffff",
              borderWidth: 1.2,
              shadowBlur: 14,
              shadowColor: isDark ? "rgba(255,138,168,0.26)" : "rgba(255,138,168,0.2)"
            }
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: isDark ? "rgba(255,138,168,0.14)" : "rgba(255,138,168,0.16)" },
              { offset: 1, color: "rgba(255,138,168,0)" }
            ])
          },
          z: 3
        }
      ]
    };
  }, [dataset, isDark, locale, reduceMotion]);

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

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    const instance = echarts.init(chartRef.current, undefined, {
      renderer: "canvas"
    });

    chartInstanceRef.current = instance;

    const resizeObserver = new ResizeObserver(() => {
      instance.resize();
    });

    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      instance.dispose();
      chartInstanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartInstanceRef.current?.setOption(option, true);
  }, [option]);

  return (
    <section
      className={twMerge(
        "relative overflow-hidden rounded-xl bg-white p-4 shadow-sm dark:border dark:border-white/8 dark:bg-slate-950/88 dark:shadow-[0_16px_48px_rgba(2,6,23,0.26)] md:p-5",
        className
      )}
    >
      <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-full bg-slate-100/94 p-1 shadow-sm ring-1 ring-slate-200/70 backdrop-blur-sm dark:bg-slate-900/84 dark:ring-white/8 md:right-5 md:top-5">
        {WINDOW_OPTIONS.map((item) => {
          const active = item === windowSize;

          return (
            <button
              className={twMerge(
                "rounded-full px-3 py-1.5 text-xs font-medium transition-colors duration-150",
                active
                  ? "bg-peach-500 text-white shadow-sm"
                  : "text-slate-500 hover:bg-white/80 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/8 dark:hover:text-white"
              )}
              key={item}
              onClick={() => {
                startTransition(() => setWindowSize(item));
              }}
              type="button"
            >
              {COPY[locale].windows[item]}
            </button>
          );
        })}
      </div>

      <div className="relative h-[18rem] w-full md:h-[20rem]">
        <div className="h-full w-full" ref={chartRef} />
      </div>
    </section>
  );
}
