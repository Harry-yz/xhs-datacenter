import { ReactNode } from "react";

type DashboardHeroProps = {
  eyebrow?: string;
  breadcrumb?: string;
  title: string;
  description: string;
  rightSlot?: ReactNode;
  compact?: boolean;
};

export function DashboardHero({ eyebrow, breadcrumb, title, description, rightSlot, compact = false }: DashboardHeroProps) {
  return (
    <section className={`grid xl:grid-cols-[1.05fr_0.95fr] ${compact ? "gap-3.5" : "gap-6"}`}>
      <div
        className={`section-frame subtle-grid relative overflow-hidden ${
          compact ? "p-4 md:p-5 !backdrop-blur-sm !shadow-sm" : ""
        }`}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,166,107,0.16),transparent_24rem)]" />
        <div className="relative">
          {breadcrumb ? <div className="text-xs uppercase tracking-[0.26em] text-foreground/42">{breadcrumb}</div> : null}
          {eyebrow ? (
            <span className="text-xs uppercase tracking-[0.28em] text-foreground/42">{eyebrow}</span>
          ) : null}
          <h1
            className={`text-foreground ${
              compact ? "mt-1.5 text-[1.5rem] font-medium leading-tight sm:text-[1.65rem] md:text-[1.8rem]" : "mt-4"
            }`}
          >
            {title}
          </h1>
          <p
            className={`max-w-2xl text-foreground/66 ${
              compact ? "mt-1.5 text-xs leading-relaxed md:text-sm" : "mt-4"
            }`}
          >
            {description}
          </p>
        </div>
      </div>
      {rightSlot ? <div>{rightSlot}</div> : null}
    </section>
  );
}
