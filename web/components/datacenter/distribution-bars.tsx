export function DistributionBars({
  title,
  items
}: {
  title: string;
  items: Array<{ label: string; value: number }>;
}) {
  const max = Math.max(...items.map((item) => item.value), 1);
  const total = items.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="section-frame overflow-hidden">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{title}</div>
          <div className="mt-2 font-display text-2xl tracking-tight text-foreground">{total}</div>
        </div>
      </div>
      <div className="space-y-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-sm text-foreground/70">
              <span>{item.label}</span>
              <span>{item.value}%</span>
            </div>
            <div className="h-2.5 rounded-full bg-foreground/8">
              <div
                className="h-2.5 rounded-full bg-gradient-to-r from-[#ff9d66] via-[#f3b9cf] to-[#98d5ff]"
                style={{ width: `${(item.value / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
