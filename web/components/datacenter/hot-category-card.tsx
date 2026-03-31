import Link from "next/link";

import { type HotCategoryVM } from "@/types/datacenter";

export function HotCategoryCard({ item, href }: { item: HotCategoryVM; href: string }) {
  return (
    <Link
      className="section-frame min-w-[270px] overflow-hidden transition duration-300 hover:-translate-y-1 hover:border-border/55 hover:shadow-card-hover"
      href={href}
    >
      <div className="mb-5 h-px w-16 bg-gradient-to-r from-accent/70 to-transparent" />
      <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{item.notes}</div>
      <div className="mt-4 flex items-start justify-between gap-4">
        <div>
          <div className="font-display text-2xl text-foreground">{item.name}</div>
          <p className="mt-2 text-sm text-foreground/66">{item.description}</p>
        </div>
        <div className="rounded-full bg-accent/10 px-3 py-1 text-sm text-accent">{item.change}</div>
      </div>
    </Link>
  );
}
