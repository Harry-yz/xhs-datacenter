import { type StatusStat } from "@/types/datacenter";

export function StatusOverviewStrip({ items }: { items: StatusStat[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="section-frame relative overflow-hidden py-5">
          <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-accent/50 to-transparent" />
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/42">{item.label}</div>
          <div className="mt-3 font-display text-2xl tracking-tight text-foreground">{item.value}</div>
          {item.helper ? <div className="mt-2 text-sm text-foreground/52">{item.helper}</div> : null}
        </div>
      ))}
    </div>
  );
}
