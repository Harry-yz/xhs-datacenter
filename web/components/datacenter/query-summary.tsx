import { type MetricValue } from "@/types/datacenter";

export function QuerySummary({ items }: { items: MetricValue[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="section-frame">
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{item.label}</div>
          <div className="metric-number mt-4">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
