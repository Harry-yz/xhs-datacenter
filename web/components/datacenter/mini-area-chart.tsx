import { type TrendPoint } from "@/types/datacenter";

function buildPoints(items: TrendPoint[]) {
  if (!items.length) {
    return "";
  }

  const max = Math.max(...items.map((item) => item.value));
  const min = Math.min(...items.map((item) => item.value));
  const range = Math.max(max - min, 1);

  return items
    .map((item, index) => {
      const x = (index / Math.max(items.length - 1, 1)) * 100;
      const y = 100 - ((item.value - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");
}

export function MiniAreaChart({
  items,
  eyebrow,
  title,
  periodLabel
}: {
  items: TrendPoint[];
  eyebrow?: string;
  title?: string;
  periodLabel?: string;
}) {
  const points = buildPoints(items);
  const latest = items.at(-1)?.value ?? 0;
  const previous = items.at(-2)?.value ?? latest;
  const delta = previous === 0 ? 0 : ((latest - previous) / previous) * 100;
  const chartId = items.map((item) => item.label).join("-").replace(/[^a-zA-Z0-9-]/g, "").slice(0, 32) || "chart";

  return (
    <div className="section-frame overflow-hidden">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{eyebrow ?? "Trend"}</div>
          <div className="mt-2 font-display text-2xl tracking-tight">{title ?? "Performance Curve"}</div>
        </div>
        <div className="text-right">
          <div className="font-display text-2xl tracking-tight text-foreground">{latest.toLocaleString()}</div>
          <div className="text-sm text-accent">
            {delta >= 0 ? "+" : ""}
            {delta.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="relative h-64">
        <svg className="h-full w-full" preserveAspectRatio="none" viewBox="0 0 100 100">
          <defs>
            <linearGradient id={`${chartId}-area`} x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="rgba(255,157,102,0.72)" />
              <stop offset="100%" stopColor="rgba(134,198,255,0.12)" />
            </linearGradient>
            <linearGradient id={`${chartId}-line`} x1="0%" x2="100%" y1="0%" y2="0%">
              <stop offset="0%" stopColor="rgba(255, 172, 112, 0.95)" />
              <stop offset="100%" stopColor="rgba(152, 213, 255, 0.9)" />
            </linearGradient>
          </defs>
          {[20, 40, 60, 80].map((y) => (
            <line
              key={y}
              stroke="rgba(255,255,255,0.08)"
              strokeDasharray="2 3"
              strokeWidth="0.6"
              x1="0"
              x2="100"
              y1={y}
              y2={y}
            />
          ))}
          <path d={`M0,100 ${points} 100,100 Z`} fill={`url(#${chartId}-area)`} opacity="0.8" />
          <polyline
            fill="none"
            points={points}
            stroke={`url(#${chartId}-line)`}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2.2"
          />
        </svg>
        <div className="absolute right-4 top-3 rounded-full border border-border/20 bg-background/60 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-foreground/55 backdrop-blur-md">
          {periodLabel ?? "7D"}
        </div>
        <div className="absolute inset-x-0 bottom-0 flex justify-between text-xs text-foreground/42">
          {items.map((item) => (
            <span key={item.label}>{item.label}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
