"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import type { Locale } from "@/config/i18n";
import { SearchBar } from "@/components/datacenter/search-bar";

export type SearchViewType = "category" | "creator";

export function buildXhsSearchLabels(locale: Locale) {
  const isZh = locale === "zh";
  return {
    back: isZh ? "返回数据总览" : "Back to Data Overview",
    tabCategory: isZh ? "品类/品牌" : "Categories/Brands",
    tabCreator: isZh ? "达人" : "Creators",
    placeholder: "",
    search: isZh ? "搜索" : "Search",
    loadingSearch: isZh ? "搜索中..." : "Searching...",
    refresh: isZh ? "刷新" : "Refresh",
    retry: isZh ? "请求失败，请刷新重试" : "Request failed. Refresh to retry.",
    viewDetails: isZh ? "查看详情" : "View Details",
    searchResult: isZh ? "搜索结果" : "Search Result",
    noteInteractions: isZh ? "笔记互动" : "Note Interactions",
    likes: isZh ? "点赞" : "Likes",
    searchVolume: isZh ? "搜索量" : "Search Volume",
    comments: isZh ? "评论" : "Comments",
    index: isZh ? "序号" : "#",
    actions: isZh ? "操作" : "Actions",
    creatorHome: isZh ? "达人主页" : "Creator Home",
    creatorInfo: isZh ? "达人信息" : "Creator Info",
    followers: isZh ? "粉丝数" : "Followers",
    totalNotes: isZh ? "总笔记数" : "Total Notes",
    totalLikesSaves: isZh ? "总互动量" : "Total Likes/Saves",
    summary: isZh ? "数据总结" : "Summary",
    summaryNotes: isZh ? "命中笔记" : "Matched Notes",
    summaryCreators: isZh ? "命中达人" : "Matched Creators",
    summaryComments: isZh ? "评论总量" : "Total Comments",
    loadingResults: isZh ? "正在加载结果" : "Loading results",
    loadingTimeout: isZh ? "补采时间较长，请重新搜索继续获取结果" : "Fetching is taking longer than expected. Search again to continue.",
    retrySearch: isZh ? "重新搜索" : "Search Again",
  };
}

export function XhsSearchFrame({
  locale,
  selectedType,
  searchQuery,
  backHref,
  onSearch,
  onTypeChange,
  children,
  banner,
  searchBarDisabled = false,
  searchBarLoading = false,
}: {
  locale: Locale;
  selectedType: SearchViewType;
  searchQuery: string;
  backHref: string;
  onSearch: (query: string) => void;
  onTypeChange: (type: SearchViewType) => void;
  children: ReactNode;
  banner?: ReactNode;
  searchBarDisabled?: boolean;
  searchBarLoading?: boolean;
}) {
  const labels = buildXhsSearchLabels(locale);

  return (
    <div className="space-y-5">
      <Link
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 transition hover:text-[#ff7fa5]"
        href={backHref}
      >
        <ArrowLeft className="h-4 w-4" />
        {labels.back}
      </Link>

      <SearchBar
        categoryLabel={labels.tabCategory}
        creatorLabel={labels.tabCreator}
        currentType={selectedType}
        disabled={searchBarDisabled}
        loading={searchBarLoading}
        onSearch={onSearch}
        onTypeChange={onTypeChange}
        placeholder={labels.placeholder}
        searchButtonLabel={searchBarLoading ? labels.loadingSearch : labels.search}
        searchQuery={searchQuery}
      />

      {banner}
      {children}
    </div>
  );
}

export function XhsSearchPanelsSkeleton({
  locale,
  activeType,
  message,
}: {
  locale: Locale;
  activeType: SearchViewType;
  message?: string;
}) {
  const labels = buildXhsSearchLabels(locale);
  const isCreator = activeType === "creator";

  return (
    <>
      <section className="rounded-xl border border-slate-100 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left">
            <thead className="border-b border-slate-100 bg-slate-50/70">
              <tr>
                <th className="w-16 px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.index}</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-500">
                  {isCreator ? labels.creatorInfo : labels.searchResult}
                </th>
                {isCreator ? (
                  <>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.followers}</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.totalNotes}</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.totalLikesSaves}</th>
                  </>
                ) : (
                  <>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.noteInteractions}</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.likes}</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.searchVolume}</th>
                    <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.comments}</th>
                  </>
                )}
                <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.actions}</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 8 }).map((_, idx) => (
                <tr className="border-b border-slate-100/80" key={`skeleton-row-${idx}`}>
                  <td className="px-4 py-3">
                    <div className="ml-auto h-4 w-8 animate-pulse rounded bg-slate-100" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="space-y-2">
                      <div className="h-4 w-40 animate-pulse rounded bg-slate-100" />
                      <div className="h-3 w-24 animate-pulse rounded bg-slate-50" />
                    </div>
                  </td>
                  {Array.from({ length: isCreator ? 3 : 4 }).map((__, metricIdx) => (
                    <td className="px-4 py-3" key={`metric-${idx}-${metricIdx}`}>
                      <div className="ml-auto h-4 w-14 animate-pulse rounded bg-slate-100" />
                    </td>
                  ))}
                  <td className="px-4 py-3">
                    <div className="ml-auto h-4 w-16 animate-pulse rounded bg-peach-50" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 pb-3 pt-2 text-xs text-slate-400">{message ?? labels.loadingResults}</div>
        </div>
      </section>

      <section className="flex items-center justify-center gap-2">
        <div className="h-9 w-12 animate-pulse rounded-lg border border-slate-200 bg-white" />
        {Array.from({ length: 5 }).map((_, idx) => (
          <div className="h-9 w-10 animate-pulse rounded-lg bg-peach-50" key={`page-skeleton-${idx}`} />
        ))}
        <div className="h-9 w-12 animate-pulse rounded-lg border border-slate-200 bg-white" />
      </section>

      <section className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3 shadow-sm">
        <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">{labels.summary}</div>
        <div className="grid gap-2.5 sm:grid-cols-3">
          {[labels.summaryNotes, labels.summaryCreators, labels.summaryComments].map((label) => (
            <article className="rounded-lg border border-slate-100 bg-white px-3 py-2" key={label}>
              <div className="text-[11px] text-slate-500">{label}</div>
              <div className="mt-1 h-5 w-20 animate-pulse rounded bg-slate-100" />
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
