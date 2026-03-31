export function StackedAudienceBars({
  title,
  items
}: {
  title: string;
  items: Array<{ label: string; value: number }>;
}) {
  return (
    <div className="section-frame">
      <div className="mb-6 text-xs uppercase tracking-[0.22em] text-foreground/45">{title}</div>
      <div className="space-y-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-sm text-foreground/72">
              <span>{item.label}</span>
              <span>{item.value}%</span>
            </div>
            <div className="h-2 rounded-full bg-foreground/8">
              <div
                className="h-2 rounded-full bg-gradient-to-r from-[#ffad78] to-[#9fd7ff]"
                style={{ width: `${item.value}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
