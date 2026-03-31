import Link from "next/link";
import { MouseEventHandler } from "react";

import { type IndustryCardVM } from "@/types/datacenter";

export function IndustryCard({
  item,
  href,
  onClick,
}: {
  item: IndustryCardVM;
  href?: string;
  onClick?: MouseEventHandler<HTMLAnchorElement>;
}) {
  const content = (
    <div className="rounded-3xl border border-border/25 bg-background/56 p-5 shadow-sm backdrop-blur-sm transition duration-200 hover:border-border/50 hover:bg-background/68 hover:shadow-md">
      <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{item.value}</div>
      <div className="mt-4 font-display text-xl text-foreground">{item.name}</div>
      <p className="mt-2 text-sm text-foreground/66">{item.description}</p>
    </div>
  );

  return href ? (
    <Link href={href} onClick={onClick}>
      {content}
    </Link>
  ) : (
    content
  );
}
