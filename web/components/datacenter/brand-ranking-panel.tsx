import Link from "next/link";

import { type Locale } from "@/config/i18n";
import { type BrandRankingItem } from "@/types/datacenter";
import { withLocale } from "@/utils/routes";

export function BrandRankingPanel({
  items,
  locale,
  eyebrow,
  title,
  primaryLabel,
  secondaryLabel,
  creatorUnit,
  contentUnit
}: {
  items: BrandRankingItem[];
  locale: Locale;
  eyebrow: string;
  title: string;
  primaryLabel: string;
  secondaryLabel: string;
  creatorUnit: string;
  contentUnit: string;
}) {
  return (
    <div className="section-frame overflow-hidden">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-foreground/45">{eyebrow}</div>
          <div className="mt-2 font-display text-2xl tracking-tight">{title}</div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="rounded-full border border-accent/25 bg-accent/12 px-3 py-1 text-foreground">{primaryLabel}</span>
          <span className="rounded-full border border-border/30 bg-foreground/5 px-3 py-1 text-foreground/55">{secondaryLabel}</span>
        </div>
      </div>

      <div className="space-y-4">
        {items.map((item, index) => (
          <Link
            key={item.slug}
            className="grid grid-cols-[32px_1fr_auto] items-center gap-4 rounded-2xl border border-border/20 bg-foreground/5 px-4 py-4 transition duration-300 hover:border-border/55 hover:bg-foreground/8"
            href={withLocale(locale, `/datacenter/xhs/brand/${item.slug}`)}
          >
            <div className="font-display text-2xl text-foreground/35">{index + 1}</div>
            <div>
              <div className="text-base font-medium text-foreground">{item.brandName}</div>
              <div className="mt-1 text-xs uppercase tracking-[0.18em] text-foreground/48">
                {item.creatorCount} {creatorUnit} / {item.contentCount} {contentUnit}
              </div>
              <div className="mt-3 h-1.5 w-full rounded-full bg-foreground/8">
                <div
                  className="h-1.5 rounded-full bg-gradient-to-r from-[#ff9d66] via-[#f3b9cf] to-[#98d5ff]"
                  style={{ width: `${76 - index * 12}%` }}
                />
              </div>
            </div>
            <div className="text-right">
              <div className="font-display text-2xl text-foreground">{item.engagementTotal}</div>
              <div className="text-sm text-accent">{item.trendDelta}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
