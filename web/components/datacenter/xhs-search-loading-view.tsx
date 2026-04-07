"use client";

import { useMemo } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import type { Locale } from "@/config/i18n";
import {
  type SearchViewType,
  XhsSearchFrame,
  XhsSearchPanelsSkeleton,
  buildXhsSearchLabels,
} from "@/components/datacenter/xhs-search-shell";

function detectLocale(pathname: string): Locale {
  return pathname.startsWith("/en/") || pathname === "/en" ? "en" : "zh";
}

export function XhsSearchLoadingView() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const locale = detectLocale(pathname);
  const labels = useMemo(() => buildXhsSearchLabels(locale), [locale]);
  const type: SearchViewType = searchParams.get("type") === "creator" ? "creator" : "category";
  const query = (searchParams.get("q") ?? "").trim();

  return (
    <XhsSearchFrame
      backHref={`/${locale}/datacenter/xhs`}
      banner={
        <section className="rounded-xl border border-peach-200/50 bg-peach-50/55 px-3 py-2 text-sm text-slate-700 shadow-sm">
          <div className="inline-flex items-center gap-2">
            <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-peach-200 border-t-peach-500" />
            <span>{labels.loadingResults}</span>
          </div>
        </section>
      }
      locale={locale}
      onSearch={() => {}}
      onTypeChange={() => {}}
      searchBarDisabled
      searchBarLoading
      searchQuery={query}
      selectedType={type}
    >
      <XhsSearchPanelsSkeleton activeType={type} locale={locale} message={labels.loadingResults} />
    </XhsSearchFrame>
  );
}
