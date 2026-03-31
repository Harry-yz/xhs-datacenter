import { type FilterChip } from "@/types/datacenter";
import { cn } from "@/utils/cn";

export function FilterChipBar({ items }: { items: FilterChip[] }) {
  return (
    <div className="section-frame flex flex-wrap gap-3">
      {items.map((item) => (
        <div
          key={`${item.label}-${item.value}`}
          className={cn(
            "rounded-full border px-4 py-2 text-sm transition duration-300",
            item.active
              ? "border-accent/35 bg-accent/12 text-foreground shadow-[0_0_0_1px_rgba(255,152,90,0.12)]"
              : "border-border/25 bg-foreground/5 text-foreground/68"
          )}
        >
          <span className="text-foreground/45">{item.label}</span>
          <span className="ml-2 text-foreground">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
