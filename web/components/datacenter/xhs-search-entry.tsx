"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { flushSync } from "react-dom";

import { type Locale } from "@/config/i18n";
import { SearchBar, type SearchTypeOption } from "@/components/datacenter/search-bar";
import { useAuthModal } from "@/components/providers/auth-modal-provider";

export function XhsSearchEntry({
  locale,
  authenticated,
  backHref,
  searchPath,
  defaultQuery = ""
}: {
  locale: Locale;
  authenticated: boolean;
  backHref: string;
  searchPath: string;
  defaultQuery?: string;
}) {
  const isZh = locale === "zh";
  const router = useRouter();
  const auth = useAuthModal();
  const [query, setQuery] = useState(defaultQuery);
  const [searchType, setSearchType] = useState<SearchTypeOption>("category");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const texts = useMemo(
    () => ({
      back: isZh ? "返回数据中心" : "Back",
      title: isZh ? "小红书" : "XiaoHongShu",
      helper: isZh ? "输入关键词后可按品类或达人检索" : "Search by category or creator",
      placeholder: "",
      submit: isZh ? "开始搜索" : "Search",
      category: isZh ? "品类" : "Category",
      creator: isZh ? "达人" : "Creator",
    }),
    [isZh]
  );

  function buildTarget(nextType: SearchTypeOption, nextQuery: string) {
    const params = new URLSearchParams();
    params.set("type", nextType);
    params.set("q", nextQuery.trim());
    return `${searchPath}?${params.toString()}`;
  }

  function submitSearch(nextQuery: string) {
    const trimmed = nextQuery.trim();

    if (!trimmed) {
      return;
    }

    const target = buildTarget(searchType, trimmed);
    // Auth gate must remain for the search entry.
    if (authenticated || auth.authenticated) {
      flushSync(() => {
        setIsSubmitting(true);
      });
      router.push(target);
      return;
    }
    auth.openAuthModal({ next: target });
  }

  return (
    <>
      <section className="section-frame !backdrop-blur-sm !shadow-sm px-4 py-4 md:px-5 md:py-4">
        <div className="mb-3 flex items-center justify-between">
          <Link
            className="inline-flex items-center gap-2 rounded-full border border-border/35 bg-background/60 px-3 py-1.5 text-xs text-foreground/70 transition hover:border-border/65 hover:text-foreground"
            href={backHref}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            {texts.back}
          </Link>
        </div>

        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.2em] text-foreground/45">{texts.title}</div>
          <h2 className="mt-1.5 text-[1.35rem] font-medium tracking-tight text-foreground md:text-[1.55rem]">{isZh ? "数据中心" : "Data Center"}</h2>
          <p className="mt-0.5 text-xs text-foreground/62 md:text-[13px]">{texts.helper}</p>
          <SearchBar
            categoryLabel={isZh ? "品类/品牌" : "Categories/Brands"}
            className="mt-4"
            creatorLabel={texts.creator}
            currentType={searchType}
            disabled={isSubmitting}
            loading={isSubmitting}
            onSearch={(value) => {
              setQuery(value);
              submitSearch(value);
            }}
            onTypeChange={(nextType) => {
              if (isSubmitting) {
                return;
              }
              setSearchType(nextType);
            }}
            placeholder={texts.placeholder}
            searchButtonLabel={texts.submit}
            searchQuery={query}
          />
        </div>
      </section>
    </>
  );
}
