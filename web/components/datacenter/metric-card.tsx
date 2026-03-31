import { cn } from "@/utils/cn";
import { type DashboardKPI } from "@/types/datacenter";

export function MetricCard({ item, compact = false }: { item: DashboardKPI; compact?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-3xl border border-border/30 bg-background/60 shadow-card backdrop-blur-xl transition duration-300 hover:border-border/55 hover:shadow-card-hover",
        compact
          ? "p-3 md:p-3.5 !backdrop-blur-sm !shadow-sm hover:!shadow-md"
          : "p-5",
        item.tone === "accent" && "bg-accent/8"
      )}
    >
      <div className={cn("font-light uppercase tracking-[0.2em] text-foreground/45", compact ? "text-[11px]" : "text-xs")}>
        {item.label}
      </div>
      <div className={cn(compact ? "mt-2 font-display text-[1.35rem] font-medium tracking-tight md:text-[1.5rem]" : "metric-number mt-4")}>
        {item.value}
      </div>
      {item.change ? (
        <div className={cn("font-light text-accent", compact ? "mt-1 text-[11px]" : "mt-2 text-sm")}>{item.change}</div>
      ) : null}
    </div>
  );
}
