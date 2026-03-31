"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import type { Locale } from "@/config/i18n";
import type { CreatorOpportunityVM, NoteAnalysisCardVM } from "@/types/datacenter";
import { SearchBar } from "@/components/datacenter/search-bar";
import { useAuthModal } from "@/components/providers/auth-modal-provider";

type SearchType = "category" | "creator";
type SortOrder = "asc" | "desc";
type CategorySortKey = "stat" | "like" | "read" | "comments";
type CreatorSortKey = "followers" | "notes" | "sumStat";
type SortKey = CategorySortKey | CreatorSortKey;

type CategoryRowVM = {
  id: string;
  avatar: string;
  name: string;
  subtitle: string;
  stat: number;
  like: number;
  read: number;
  comments: number;
};

type CreatorRowVM = {
  id: string;
  avatar: string;
  name: string;
  followers: number;
  notes: number;
  sumStat: number;
  direction: string;
};

const PAGE_SIZE = 30;

const CATEGORY_SORT_KEYS: CategorySortKey[] = ["stat", "like", "read", "comments"];
const CREATOR_SORT_KEYS: CreatorSortKey[] = ["followers", "notes", "sumStat"];

function parseCount(value: string | number | undefined) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : 0;
  }
  if (!value) {
    return 0;
  }

  const normalized = String(value).trim().replace(/,/g, "").toLowerCase();
  if (normalized.endsWith("k")) {
    return Math.round(Number.parseFloat(normalized.slice(0, -1)) * 1000);
  }
  if (normalized.endsWith("m")) {
    return Math.round(Number.parseFloat(normalized.slice(0, -1)) * 1000000);
  }
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? Math.round(parsed) : 0;
}

function toAvatarLetter(value: string) {
  const first = value.trim().charAt(0);
  return first ? first.toUpperCase() : "X";
}

function toNumberLabel(value: number, locale: Locale) {
  return value.toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function updateParams(
  pathname: string,
  current: { toString(): string },
  changes: Record<string, string | undefined>
) {
  const next = new URLSearchParams(current.toString());
  Object.entries(changes).forEach(([key, value]) => {
    if (!value) {
      next.delete(key);
      return;
    }
    next.set(key, value);
  });
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function isCategorySortKey(value: string): value is CategorySortKey {
  return CATEGORY_SORT_KEYS.includes(value as CategorySortKey);
}

function isCreatorSortKey(value: string): value is CreatorSortKey {
  return CREATOR_SORT_KEYS.includes(value as CreatorSortKey);
}

function getPageWindow(page: number, pageCount: number) {
  if (pageCount <= 5) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  const start = Math.max(1, Math.min(page - 2, pageCount - 4));
  return Array.from({ length: 5 }, (_, index) => start + index);
}

export function XhsSearchResultsView({
  locale,
  initialQuery,
  notes,
  creators,
  resultTotals,
  pending,
  requireAuth = false
}: {
  locale: Locale;
  initialQuery: string;
  notes: NoteAnalysisCardVM[];
  creators: CreatorOpportunityVM[];
  resultTotals?: {
    category: number;
    creator: number;
    page: number;
    size: number;
  };
  pending?: {
    status: "pending" | "failed";
    type: "category" | "creator";
    jobId?: string;
  };
  requireAuth?: boolean;
}) {
  const isZh = locale === "zh";
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentQueryString = searchParams.toString();
  const auth = useAuthModal();
  const [inputValue, setInputValue] = useState(initialQuery);

  const derivedCategoryRows: CategoryRowVM[] = useMemo(() => {
    return notes.map((item, index) => {
      const like = parseCount(item.likeCount);
      const save = parseCount(item.collectionCount);
      const comments = parseCount(item.commentCount);
      const stat = like + save + comments;
      const read = Math.round(stat * 6.2);
      const avatar = toAvatarLetter(item.author);
      return {
        id: item.noteId,
        avatar,
        name: item.title,
        subtitle: item.author,
        stat,
        like,
        read,
        comments
      };
    });
  }, [notes]);

  const derivedCreatorRows: CreatorRowVM[] = useMemo(() => {
    const noteAgg = new Map<string, { notes: number; sumStat: number }>();

    derivedCategoryRows.forEach((item) => {
      const authorKey = item.subtitle.toLowerCase();
      const existing = noteAgg.get(authorKey) ?? { notes: 0, sumStat: 0 };
      noteAgg.set(authorKey, {
        notes: existing.notes + 1,
        sumStat: existing.sumStat + item.stat
      });
    });

    const baseRows = creators.map((item) => {
      const key = item.name.toLowerCase();
      const stat = noteAgg.get(key);
      const followers = parseCount(item.followers);
      const notesCount =
        typeof item.notesCount === "number" && item.notesCount > 0
          ? item.notesCount
          : (stat?.notes ?? 0);
      const sumStat =
        typeof item.totalInteractions === "number" && item.totalInteractions > 0
          ? item.totalInteractions
          : (stat?.sumStat ?? 0);
      return {
        id: item.name,
        avatar: toAvatarLetter(item.name),
        name: item.name,
        followers,
        notes: notesCount,
        sumStat,
        direction: item.direction
      };
    });

    if (baseRows.length > 0) {
      return baseRows;
    }

    return Array.from(noteAgg.entries()).map(([name, stat]) => ({
      id: name,
      avatar: toAvatarLetter(name),
      name,
      followers: 0,
      notes: stat.notes,
      sumStat: stat.sumStat,
      direction: isZh ? "内容达人" : "Content Creator"
    }));
  }, [creators, derivedCategoryRows, isZh]);

  const activeType: SearchType = searchParams.get("type") === "creator" ? "creator" : "category";
  const query = (searchParams.get("q") ?? initialQuery).trim() || initialQuery;
  const defaultSort: SortKey = activeType === "creator" ? "followers" : "stat";
  const sortParam = searchParams.get("sort") ?? defaultSort;
  const orderParam = searchParams.get("order") === "asc" ? "asc" : "desc";
  const pageParam = Math.max(1, parseCount(searchParams.get("page") ?? "1"));

  const sortKey: SortKey =
    activeType === "creator"
      ? isCreatorSortKey(sortParam)
        ? sortParam
        : "followers"
      : isCategorySortKey(sortParam)
        ? sortParam
        : "stat";

  const order: SortOrder = orderParam;

  useEffect(() => {
    setInputValue(query);
  }, [query]);

  useEffect(() => {
    if (!requireAuth || auth.authenticated) {
      return;
    }
    const current = currentQueryString ? `${pathname}?${currentQueryString}` : pathname;
    auth.openAuthModal({ next: current });
  }, [auth, currentQueryString, pathname, requireAuth]);

  const filteredCategoryRows = useMemo(() => derivedCategoryRows, [derivedCategoryRows]);

  const filteredCreatorRows = useMemo(() => derivedCreatorRows, [derivedCreatorRows]);

  const sortedCategoryRows = useMemo(() => {
    const rows = [...filteredCategoryRows];
    const key: CategorySortKey = isCategorySortKey(sortKey) ? sortKey : "stat";
    rows.sort((left, right) => {
      const delta = left[key] - right[key];
      return order === "asc" ? delta : -delta;
    });
    return rows;
  }, [filteredCategoryRows, order, sortKey]);

  const sortedCreatorRows = useMemo(() => {
    const rows = [...filteredCreatorRows];
    const key: CreatorSortKey = isCreatorSortKey(sortKey) ? sortKey : "followers";
    rows.sort((left, right) => {
      const delta = left[key] - right[key];
      return order === "asc" ? delta : -delta;
    });
    return rows;
  }, [filteredCreatorRows, order, sortKey]);

  const primaryRowsCount = activeType === "category"
    ? Math.max(0, Number(resultTotals?.category ?? sortedCategoryRows.length))
    : Math.max(0, Number(resultTotals?.creator ?? sortedCreatorRows.length));
  const pageCount = Math.max(1, Math.ceil(primaryRowsCount / PAGE_SIZE));
  const page = Math.min(pageParam, pageCount);
  const pageWindow = getPageWindow(page, pageCount);

  const pagedCategoryRows = sortedCategoryRows;
  const pagedCreatorRows = sortedCreatorRows;

  const summary = useMemo(() => {
    const noteTotal = Math.max(0, Number(resultTotals?.category ?? sortedCategoryRows.length));
    const creatorTotal = Math.max(0, Number(resultTotals?.creator ?? sortedCreatorRows.length));
    const totalComments = sortedCategoryRows.reduce((accumulator, item) => accumulator + item.comments, 0);
    return { noteTotal, creatorTotal, totalComments };
  }, [resultTotals, sortedCategoryRows, sortedCreatorRows]);

  const labels = {
    back: isZh ? "返回数据总览" : "Back to Data Overview",
    tabCategory: isZh ? "品类/品牌" : "Categories/Brands",
    tabCreator: isZh ? "达人" : "Creators",
    placeholder: isZh ? "输入关键词，例如：防晒、兰蔻、惊喜盒子" : "Search category, brand, or creator",
    search: isZh ? "搜索" : "Search",
    searchResult: isZh ? "搜索结果" : "Search Result",
    noteInteractions: isZh ? "笔记互动" : "Note Interactions",
    likes: isZh ? "点赞" : "Likes",
    searchVolume: isZh ? "搜索量" : "Search Volume",
    comments: isZh ? "评论" : "Comments",
    index: isZh ? "序号" : "#",
    actions: isZh ? "操作" : "Actions",
    viewDetails: isZh ? "查看详情" : "View Details",
    creatorInfo: isZh ? "达人信息" : "Creator Info",
    followers: isZh ? "粉丝数" : "Followers",
    totalNotes: isZh ? "总笔记数" : "Total Notes",
    totalLikesSaves: isZh ? "总互动量" : "Total Likes/Saves",
    summary: isZh ? "数据总结" : "Summary",
    summaryNotes: isZh ? "命中笔记" : "Matched Notes",
    summaryCreators: isZh ? "命中达人" : "Matched Creators",
    summaryComments: isZh ? "评论总量" : "Total Comments",
    refresh: isZh ? "刷新" : "Refresh"
  };

  function pushWithChanges(changes: Record<string, string | undefined>) {
    const nextHref = updateParams(pathname, searchParams, changes);
    router.push(nextHref);
  }

  function onTabChange(type: SearchType) {
    if (type === activeType) {
      return;
    }

    const nextSort = type === "creator" ? "followers" : "stat";
    const target = updateParams(pathname, searchParams, {
      type,
      q: query || initialQuery,
      sort: nextSort,
      order: "desc",
      page: "1"
    });

    if (!auth.authenticated) {
      auth.openAuthModal({ next: target });
      return;
    }

    router.push(target);
  }

  function onSearch(nextQuery: string) {
    if (!auth.authenticated) {
      const target = updateParams(pathname, searchParams, {
        type: activeType,
        q: nextQuery.trim() || initialQuery,
      });
      auth.openAuthModal({ next: target });
      return;
    }

    const trimmed = nextQuery.trim();
    setInputValue(nextQuery);
    const nextSort = activeType === "creator" ? "followers" : "stat";
    pushWithChanges({
      type: activeType,
      q: trimmed || initialQuery,
      sort: nextSort,
      order: "desc",
      page: "1"
    });
  }

  function onSortChange(nextSort: SortKey) {
    if (
      (activeType === "category" && !isCategorySortKey(nextSort)) ||
      (activeType === "creator" && !isCreatorSortKey(nextSort))
    ) {
      return;
    }

    const nextOrder: SortOrder = sortKey === nextSort && order === "desc" ? "asc" : "desc";
    pushWithChanges({
      sort: nextSort,
      order: nextOrder,
      page: "1"
    });
  }

  function onPageChange(nextPage: number) {
    const safePage = Math.max(1, Math.min(pageCount, nextPage));
    pushWithChanges({
      page: String(safePage)
    });
  }

  function onBack() {
    router.push(`/${locale}/datacenter/xhs`);
  }

  function sortMark(column: SortKey) {
    if (sortKey !== column) {
      return <span className="ml-1 text-slate-300">↕</span>;
    }
    return <span className="ml-1 text-[#ff7fa5]">{order === "asc" ? "↑" : "↓"}</span>;
  }

  function sortableHeader(label: string, column: SortKey, alignRight = true) {
    const active = sortKey === column;
    return (
      <th className={`px-4 py-3 text-sm font-medium ${alignRight ? "text-right" : "text-left"}`}>
        <button
          className={`inline-flex items-center ${
            active ? "text-slate-900" : "text-slate-500 hover:text-slate-700"
          }`}
          onClick={() => onSortChange(column)}
          type="button"
        >
          {label}
          {sortMark(column)}
        </button>
      </th>
    );
  }

  return (
    <div className="space-y-5">
      <button
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 transition hover:text-[#ff7fa5]"
        onClick={onBack}
        type="button"
      >
        <ArrowLeft className="h-4 w-4" />
        {labels.back}
      </button>

      <SearchBar
        categoryLabel={labels.tabCategory}
        creatorLabel={labels.tabCreator}
        currentTab={activeType}
        onSearch={onSearch}
        onTabChange={onTabChange}
        placeholder={labels.placeholder}
        searchButtonLabel={labels.search}
        searchQuery={inputValue}
      />

      {pending?.status === "pending" ? (
        <section className="rounded-xl border border-peach-200/60 bg-peach-50/45 px-3 py-2 text-sm text-slate-700 shadow-sm">
          <button
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 transition hover:border-peach-300 hover:text-peach-600"
            onClick={() => router.refresh()}
            type="button"
          >
            {labels.refresh}
          </button>
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-100 bg-white shadow-sm">
        <div className="overflow-x-auto">
          {activeType === "category" ? (
            <table className="min-w-full text-left">
              <thead className="border-b border-slate-100 bg-slate-50/70">
                <tr>
                  <th className="w-16 px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.index}</th>
                  <th className="px-4 py-3 text-sm font-medium text-slate-500">{labels.searchResult}</th>
                  {sortableHeader(labels.noteInteractions, "stat")}
                  {sortableHeader(labels.likes, "like")}
                  {sortableHeader(labels.searchVolume, "read")}
                  {sortableHeader(labels.comments, "comments")}
                  <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.actions}</th>
                </tr>
              </thead>
              <tbody>
                {pagedCategoryRows.map((item, index) => (
                  <tr className="border-b border-slate-100/80 transition hover:bg-[#fff4f7]" key={item.id}>
                    <td className="px-4 py-2.5 text-right text-sm text-slate-500 tabular-nums">
                      {(page - 1) * PAGE_SIZE + index + 1}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="min-w-0">
                        <div className="line-clamp-1 text-sm font-medium text-slate-800">{item.name}</div>
                        <div className="mt-0.5 text-xs text-slate-500">{item.subtitle}</div>
                      </div>
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "stat" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.stat, locale)}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "like" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.like, locale)}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "read" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.read, locale)}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "comments" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.comments, locale)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link
                        className="text-sm text-peach-500 transition hover:text-peach-600"
                        href={`https://www.xiaohongshu.com/explore/${item.id}`}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {labels.viewDetails}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="min-w-full text-left">
              <thead className="border-b border-slate-100 bg-slate-50/70">
                <tr>
                  <th className="w-16 px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.index}</th>
                  <th className="px-4 py-3 text-sm font-medium text-slate-500">{labels.creatorInfo}</th>
                  {sortableHeader(labels.followers, "followers")}
                  {sortableHeader(labels.totalNotes, "notes")}
                  {sortableHeader(labels.totalLikesSaves, "sumStat")}
                  <th className="px-4 py-3 text-right text-sm font-medium text-slate-500">{labels.actions}</th>
                </tr>
              </thead>
              <tbody>
                {pagedCreatorRows.map((item, index) => (
                  <tr className="border-b border-slate-100/80 transition hover:bg-[#fff4f7]" key={item.id}>
                    <td className="px-4 py-2.5 text-right text-sm text-slate-500 tabular-nums">
                      {(page - 1) * PAGE_SIZE + index + 1}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="min-w-0">
                        <div className="line-clamp-1 text-sm font-medium text-slate-800">{item.name}</div>
                        <div className="mt-0.5 text-xs text-slate-500">{item.direction}</div>
                      </div>
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "followers" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.followers, locale)}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "notes" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.notes, locale)}
                    </td>
                    <td className={`px-4 py-2.5 text-right text-sm tabular-nums ${sortKey === "sumStat" ? "text-slate-900" : "text-slate-600"}`}>
                      {toNumberLabel(item.sumStat, locale)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <span className="text-sm text-slate-400">—</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="flex items-center justify-center gap-2">
        <button
          className="h-9 rounded-lg border border-slate-200 px-3 text-sm text-slate-500 transition hover:border-peach-500/35 hover:text-peach-500"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          type="button"
        >
          {"<"}
        </button>
        {pageWindow.map((item) => (
          <button
            className={`h-9 min-w-9 rounded-lg px-3 text-sm transition ${
              item === page
                ? "bg-peach-50 font-medium text-peach-600"
                : "text-slate-500 hover:bg-peach-50 hover:text-slate-700"
            }`}
            key={item}
            onClick={() => onPageChange(item)}
            type="button"
          >
            {item}
          </button>
        ))}
        <button
          className="h-9 rounded-lg border border-slate-200 px-3 text-sm text-slate-500 transition hover:border-peach-500/35 hover:text-peach-500"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
          type="button"
        >
          {">"}
        </button>
      </section>

      <section className="rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-3 shadow-sm">
        <div className="mb-2 text-xs uppercase tracking-[0.18em] text-slate-400">{labels.summary}</div>
        <div className="grid gap-2.5 sm:grid-cols-3">
          <article className="rounded-lg border border-slate-100 bg-white px-3 py-2">
            <div className="text-[11px] text-slate-500">{labels.summaryNotes}</div>
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">{toNumberLabel(summary.noteTotal, locale)}</div>
          </article>
          <article className="rounded-lg border border-slate-100 bg-white px-3 py-2">
            <div className="text-[11px] text-slate-500">{labels.summaryCreators}</div>
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">{toNumberLabel(summary.creatorTotal, locale)}</div>
          </article>
          <article className="rounded-lg border border-slate-100 bg-white px-3 py-2">
            <div className="text-[11px] text-slate-500">{labels.summaryComments}</div>
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">{toNumberLabel(summary.totalComments, locale)}</div>
          </article>
        </div>
      </section>
    </div>
  );
}
