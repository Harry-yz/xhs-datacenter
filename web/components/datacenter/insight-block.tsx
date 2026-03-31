export function InsightBlock({
  title,
  items
}: {
  title: string;
  items: string[];
}) {
  return (
    <div className="section-frame h-full">
      <div className="mb-5 text-xs uppercase tracking-[0.22em] text-foreground/45">{title}</div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item} className="rounded-2xl border border-border/20 bg-foreground/5 px-4 py-3 text-sm text-foreground/75">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
