import { ReactNode } from "react";

export function SectionHeading({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-2">
        {eyebrow ? <span className="text-xs font-light uppercase tracking-[0.28em] text-foreground/45">{eyebrow}</span> : null}
        <h2 className="text-2xl md:text-3xl">{title}</h2>
        {description ? <p className="max-w-2xl text-sm md:text-base">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
