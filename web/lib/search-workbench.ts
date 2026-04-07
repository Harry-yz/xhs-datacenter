import { type Locale } from "@/config/i18n";
import {
  type CreatorOpportunityVM,
  type NoteAnalysisCardVM,
  type SearchResultsSliceVM,
} from "@/types/datacenter";

export type SearchType = "category" | "creator";

type SearchPending = SearchResultsSliceVM["pending"];

type SearchPayload = Record<string, unknown>;

function choose(locale: Locale, zh: string, en: string) {
  return locale === "zh" ? zh : en;
}

function toLocaleCount(locale: Locale, value: number) {
  return Math.max(0, Math.round(value)).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function toCompactFollowers(locale: Locale, value: number) {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2).replace(/\.00$/, "")}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return toLocaleCount(locale, value);
}

export function mapNoteRows(locale: Locale, rows: Array<Record<string, unknown>>): NoteAnalysisCardVM[] {
  const coverPalette = [
    "from-[#f7c7b8] via-[#f1b8d6] to-[#a7d8ff]",
    "from-[#f5d29d] via-[#f1c1cf] to-[#bfdef5]",
    "from-[#a7dbdb] via-[#b9dcff] to-[#e6caff]",
  ];

  return rows.map((item, index) => {
    const noteId = String(item.note_id ?? item.noteId ?? `note-${index + 1}`);
    const title = String(item.title ?? (locale === "zh" ? "未命名笔记" : "Untitled Note"));
    const author = String(item.author_nickname ?? item.author ?? (locale === "zh" ? "匿名作者" : "Unknown Author"));

    const likeCount = Number(item.like_count ?? item.likeCount ?? 0);
    const collectionCount = Number(item.collection_count ?? item.collectionCount ?? 0);
    const commentCount = Number(item.comment_count ?? item.commentCount ?? 0);
    const readCount = Number(item.read_count ?? item.readCount ?? 0);
    const interactionTotal = Number(item.interaction_total ?? item.interactionTotal ?? (likeCount + collectionCount + commentCount));
    const followers = Number(item.followers ?? item.author_fans_count ?? item.authorFansCount ?? 0);
    const tags = Array.isArray(item.tags) ? item.tags.map(String) : [];

    return {
      noteId,
      coverColor: coverPalette[index % coverPalette.length],
      title,
      author,
      followers: toCompactFollowers(locale, followers),
      likeCount: toLocaleCount(locale, likeCount),
      likeCountValue: likeCount,
      collectionCount: toLocaleCount(locale, collectionCount),
      collectionCountValue: collectionCount,
      commentCount: toLocaleCount(locale, commentCount),
      commentCountValue: commentCount,
      readCount,
      interactionTotal,
      tags: tags.slice(0, 3),
      aiLabels: [],
    };
  });
}

export function mapCreatorRows(locale: Locale, rows: Array<Record<string, unknown>>): CreatorOpportunityVM[] {
  return rows.map((item, index) => {
    const authorId = String(item.author_id ?? item.authorId ?? "").trim();
    const name = String(item.author_nickname ?? item.name ?? authorId ?? "");
    const followers = Number(item.followers ?? item.fans_count ?? 0);
    const notesCount = Number(item.note_count ?? item.notes ?? 0);
    const totalInteractions = Number(item.interaction_total ?? item.sumStat ?? 0);
    const tags = Array.isArray(item.tags) ? item.tags.map(String).filter(Boolean) : [];
    const direction = tags.length ? tags.slice(0, 2).join(" / ") : choose(locale, "内容达人", "Content Creator");
    const rawProfileUrl = String(item.creator_home_url ?? item.anchor_link ?? item.profile_url ?? "").trim();
    const profileUrl = rawProfileUrl || (authorId ? `https://www.xiaohongshu.com/user/profile/${authorId}` : "");

    return {
      authorId: authorId || `creator-${index + 1}`,
      name: name || choose(locale, "未知达人", "Unknown Creator"),
      followers: toCompactFollowers(locale, followers),
      followersValue: followers,
      direction,
      cpe: "-",
      notesCount,
      totalInteractions,
      profileUrl,
    };
  });
}

export function createDefaultSearchPayload(page: number, size: number): SearchPayload {
  return {
    status: "ready",
    items: [],
    notes: [],
    summary: {},
    pagination: { total: 0, page, size, has_more: false },
  };
}

function resolvePending(payload: SearchPayload, type: SearchType): SearchPending {
  const status = String(payload.status ?? "");
  const pendingReasonRaw = payload.pending_reason;
  const pendingReason =
    typeof pendingReasonRaw === "string" && pendingReasonRaw.trim() ? pendingReasonRaw.trim() : undefined;
  const nextPollRaw = Number(payload.next_poll_after_ms ?? Number.NaN);
  const nextPollAfterMs = Number.isFinite(nextPollRaw) && nextPollRaw > 0 ? Math.round(nextPollRaw) : undefined;
  const freshnessRaw = Number(payload.data_freshness_seconds ?? Number.NaN);
  const dataFreshnessSeconds = Number.isFinite(freshnessRaw) && freshnessRaw >= 0 ? Math.round(freshnessRaw) : undefined;

  if (status === "pending" || status === "running") {
    const jobId = String(payload.job_id ?? "");
    return {
      status: "pending",
      type,
      jobId: jobId || undefined,
      pendingReason,
      nextPollAfterMs,
      dataFreshnessSeconds,
    };
  }
  if (status === "failed") {
    const jobId = String(payload.job_id ?? "");
    return {
      status: "failed",
      type,
      jobId: jobId || undefined,
      pendingReason,
      dataFreshnessSeconds,
    };
  }
  return undefined;
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export function buildSearchResultsSlice(params: {
  locale: Locale;
  activeType: SearchType;
  payload: SearchPayload;
  page: number;
  size: number;
}): SearchResultsSliceVM {
  const { locale, activeType, payload, page, size } = params;
  const itemsRaw = Array.isArray(payload.items) ? (payload.items as Array<Record<string, unknown>>) : [];
  const notesRaw = Array.isArray(payload.notes) ? (payload.notes as Array<Record<string, unknown>>) : [];
  const pagination = toRecord(payload.pagination);
  const summary = toRecord(payload.summary);

  const notes = activeType === "category" ? mapNoteRows(locale, itemsRaw) : mapNoteRows(locale, notesRaw);
  const creators = activeType === "creator" ? mapCreatorRows(locale, itemsRaw) : [];
  const total = Number(pagination.total ?? itemsRaw.length ?? 0);
  const hasMore = Boolean(pagination.has_more);
  const totalIsEstimate = Boolean(pagination.total_is_estimate);
  const totalComments =
    Number(summary.comment_total ?? Number.NaN) ||
    notes.reduce((sum, item) => sum + Number(item.commentCount.replace(/,/g, "")), 0);

  return {
    notes,
    creators,
    pending: resolvePending(payload, activeType),
    resultTotals: {
      category: activeType === "category" ? Math.max(0, total) : 0,
      creator: activeType === "creator" ? Math.max(0, total) : 0,
      page,
      size,
      categoryHasMore: activeType === "category" ? hasMore : false,
      creatorHasMore: activeType === "creator" ? hasMore : false,
      categoryTotalIsEstimate: activeType === "category" ? totalIsEstimate : false,
      creatorTotalIsEstimate: activeType === "creator" ? totalIsEstimate : false,
    },
    searchSummary: {
      noteTotal: Math.max(0, Number(summary.note_count ?? notes.length)),
      creatorTotal: Math.max(0, Number(summary.creator_count ?? creators.length)),
      totalComments: Math.max(0, totalComments),
    },
  };
}
