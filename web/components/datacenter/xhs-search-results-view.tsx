"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import { env } from "@/config/env";
import type { Locale } from "@/config/i18n";
import type {
  CreatorOpportunityVM,
  NoteAnalysisCardVM,
  SearchResultsSliceVM,
} from "@/types/datacenter";
import {
  XhsSearchFrame,
  XhsSearchPanelsSkeleton,
  buildXhsSearchLabels,
} from "@/components/datacenter/xhs-search-shell";
import { useAuthModal } from "@/components/providers/auth-modal-provider";

type SearchType = "category" | "creator";
type SortOrder = "asc" | "desc";
type CategorySortKey = "stat" | "like" | "read" | "comments";
type CreatorSortKey = "relevance" | "followers" | "notes" | "sumStat";
type SortKey = CategorySortKey | CreatorSortKey;

type CategoryRowVM = {
  id: string;
  name: string;
  subtitle: string;
  stat: number;
  like: number;
  read: number;
  comments: number;
};

type CreatorRowVM = {
  id: string;
  name: string;
  followers: number;
  notes: number;
  sumStat: number;
  direction: string;
  profileUrl?: string;
};

type SearchState = {
  type: SearchType;
  q: string;
  sort: SortKey;
  order: SortOrder;
  page: number;
  industry?: string;
};

type SearchUiState = "idle" | "loading" | "ready" | "pending" | "failed_timeout";

const PAGE_SIZE = 30;
const POLL_BACKOFF_MS = [2000, 3000, 5000, 8000] as const;
const SOFT_REFRESH_BACKOFF_MS = [3000, 5000, 8000] as const;
const SEARCH_TIMEOUT_MS = 60000;

const CATEGORY_SORT_KEYS: CategorySortKey[] = ["stat", "like", "read", "comments"];
const CREATOR_SORT_KEYS: CreatorSortKey[] = ["relevance", "followers", "notes", "sumStat"];
type PageToken = number | "...";

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

function toNumberLabel(value: number, locale: Locale) {
  return value.toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function isCategorySortKey(value: string): value is CategorySortKey {
  return CATEGORY_SORT_KEYS.includes(value as CategorySortKey);
}

function isCreatorSortKey(value: string): value is CreatorSortKey {
  return CREATOR_SORT_KEYS.includes(value as CreatorSortKey);
}

function createEmptyResults(type: SearchType, page: number): SearchResultsSliceVM {
  return {
    notes: [],
    creators: [],
    searchSummary: {
      noteTotal: 0,
      creatorTotal: 0,
      totalComments: 0,
    },
    pending: undefined,
    resultTotals: {
      category: 0,
      creator: 0,
      page,
      size: PAGE_SIZE,
      categoryHasMore: false,
      creatorHasMore: false,
      categoryTotalIsEstimate: false,
      creatorTotalIsEstimate: false,
    },
  };
}

function parseInitialState(initialQuery: string, initialParams?: Record<string, string>) {
  const type: SearchType = initialParams?.type === "creator" ? "creator" : "category";
  const q = (initialParams?.q ?? initialQuery).trim() || initialQuery;
  const sortParam = initialParams?.sort ?? (type === "creator" ? "relevance" : "stat");
  const sort: SortKey =
    type === "creator"
      ? (isCreatorSortKey(sortParam) ? sortParam : "relevance")
      : (isCategorySortKey(sortParam) ? sortParam : "stat");

  return {
    type,
    q,
    sort,
    order: initialParams?.order === "asc" ? "asc" : "desc",
    page: Math.max(1, parseCount(initialParams?.page ?? "1")),
    industry: initialParams?.industry?.trim() || undefined,
  } satisfies SearchState;
}

function parseStateFromUrl(search: string, fallbackQuery: string) {
  const params = new URLSearchParams(search);
  const initialParams = Object.fromEntries(params.entries());
  return parseInitialState(fallbackQuery, initialParams);
}

function buildPageTokens(currentPage: number, totalPages: number): PageToken[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const tokens: PageToken[] = [1];
  const left = Math.max(2, currentPage - 1);
  const right = Math.min(totalPages - 1, currentPage + 1);

  if (left > 2) {
    tokens.push("...");
  }
  for (let page = left; page <= right; page += 1) {
    tokens.push(page);
  }
  if (right < totalPages - 1) {
    tokens.push("...");
  }
  tokens.push(totalPages);
  return tokens;
}

function buildHref(pathname: string, state: SearchState) {
  const params = new URLSearchParams();
  params.set("type", state.type);
  params.set("q", state.q);
  params.set("sort", state.sort);
  params.set("order", state.order);
  params.set("page", String(state.page));
  if (state.type === "category" && state.industry) {
    params.set("industry", state.industry);
  }
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

function inferBrandCategoryMode(query: string): "brand" | "category" {
  const normalized = query.trim();
  if (!normalized) {
    return "category";
  }
  // Brand-like patterns: uppercase acronym, digits, hyphen/underscore combos.
  if (/[A-Z0-9]/.test(normalized) || /[-_]/.test(normalized)) {
    return "brand";
  }
  return "category";
}

function buildCacheKey(state: SearchState) {
  return JSON.stringify([
    state.type,
    state.q,
    state.sort,
    state.order,
    state.page,
    state.industry ?? "",
  ]);
}

function hasUsableRows(payload: SearchResultsSliceVM, type: SearchType) {
  if (payload.pending) {
    return false;
  }
  if (type === "creator") {
    return (payload.resultTotals?.creator ?? 0) > 0 || payload.creators.length > 0;
  }
  return (payload.resultTotals?.category ?? 0) > 0 || payload.notes.length > 0;
}

function getVisibleRowCount(payload: SearchResultsSliceVM, type: SearchType) {
  return type === "creator" ? payload.creators.length : payload.notes.length;
}

function deriveUiState(payload: SearchResultsSliceVM, type: SearchType): SearchUiState {
  const visibleRows = getVisibleRowCount(payload, type);
  if (payload.pending?.status === "pending" && visibleRows === 0) {
    return "pending";
  }
  if (payload.pending?.status === "failed" && visibleRows === 0) {
    return "failed_timeout";
  }
  if (visibleRows > 0) {
    return "ready";
  }
  return "idle";
}

function mergeStablePayload(
  previous: SearchResultsSliceVM,
  incoming: SearchResultsSliceVM,
  type: SearchType
): SearchResultsSliceVM {
  if (type === "creator") {
    const seen = new Set<string>();
    const creators = [
      ...previous.creators
        .map((item) => incoming.creators.find((candidate) => candidate.authorId === item.authorId) ?? item)
        .filter((item) => {
          if (!item.authorId || seen.has(item.authorId)) {
            return false;
          }
          seen.add(item.authorId);
          return true;
        }),
      ...incoming.creators.filter((item) => {
        if (!item.authorId || seen.has(item.authorId)) {
          return false;
        }
        seen.add(item.authorId);
        return true;
      }),
    ];
    return {
      ...incoming,
      creators,
    };
  }

  const seen = new Set<string>();
  const notes = [
    ...previous.notes
      .map((item) => incoming.notes.find((candidate) => candidate.noteId === item.noteId) ?? item)
      .filter((item) => {
        if (!item.noteId || seen.has(item.noteId)) {
          return false;
        }
        seen.add(item.noteId);
        return true;
      }),
    ...incoming.notes.filter((item) => {
      if (!item.noteId || seen.has(item.noteId)) {
        return false;
      }
      seen.add(item.noteId);
      return true;
    }),
  ];
  return {
    ...incoming,
    notes,
  };
}

async function fetchSearchSlice(
  state: SearchState,
  locale: Locale,
  signal: AbortSignal,
  forceRefresh = false
): Promise<SearchResultsSliceVM> {
  const endpoint = state.type === "creator" ? "/api/search/influencer" : "/api/search/brand-category";
  const response = await fetch(endpoint, {
    method: "POST",
    signal,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(
      state.type === "creator"
        ? {
            locale,
            query: state.q,
            industry: undefined,
            sort: state.sort,
            order: state.order,
            page: state.page,
            size: PAGE_SIZE,
            date_range: 30,
            freshness_hours: 24,
            include_notes: false,
            force_refresh: forceRefresh,
          }
        : {
            locale,
            query: state.q,
            mode: state.industry ? "category" : inferBrandCategoryMode(state.q),
            industry: state.industry,
            sort: state.sort,
            order: state.order,
            page: state.page,
            size: PAGE_SIZE,
            min_like: 1,
            date_range: 30,
            freshness_hours: 24,
            force_refresh: forceRefresh,
          }
    ),
  });

  if (!response.ok) {
    throw new Error(`search request failed with status ${response.status}`);
  }

  return (await response.json()) as SearchResultsSliceVM;
}

async function fetchSearchJobSlice(
  params: {
    jobId: string;
    state: SearchState;
    locale: Locale;
    signal: AbortSignal;
  }
): Promise<SearchResultsSliceVM> {
  const query = new URLSearchParams({
    locale: params.locale,
    type: params.state.type,
    page: String(params.state.page),
    size: String(PAGE_SIZE),
  });
  const response = await fetch(`/api/search/jobs/${encodeURIComponent(params.jobId)}?${query.toString()}`, {
    method: "GET",
    signal: params.signal,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`search job poll failed with status ${response.status}`);
  }
  return (await response.json()) as SearchResultsSliceVM;
}

export function XhsSearchResultsView({
  locale,
  initialQuery,
  notes,
  creators,
  searchSummary,
  resultTotals,
  pending,
  authenticated = false,
  requireAuth = false,
  initialParams,
}: {
  locale: Locale;
  initialQuery: string;
  notes: NoteAnalysisCardVM[];
  creators: CreatorOpportunityVM[];
  searchSummary?: SearchResultsSliceVM["searchSummary"];
  resultTotals?: {
    category: number;
    creator: number;
    page: number;
    size: number;
    categoryHasMore?: boolean;
    creatorHasMore?: boolean;
    categoryTotalIsEstimate?: boolean;
    creatorTotalIsEstimate?: boolean;
  };
  pending?: {
    status: "pending" | "failed";
    type: "category" | "creator";
    jobId?: string;
    pendingReason?: string;
    nextPollAfterMs?: number;
    dataFreshnessSeconds?: number;
  };
  authenticated?: boolean;
  requireAuth?: boolean;
  initialParams?: Record<string, string>;
}) {
  const pathname = usePathname();
  const auth = useAuthModal();
  const authAuthenticated = auth.authenticated;
  const openAuthModal = auth.openAuthModal;
  const initialState = useMemo(() => parseInitialState(initialQuery, initialParams), [initialParams, initialQuery]);
  const [searchState, setSearchState] = useState<SearchState>(initialState);
  const [draftType, setDraftType] = useState<SearchType>(initialState.type);
  const [results, setResults] = useState<SearchResultsSliceVM>({
    notes,
    creators,
    searchSummary: searchSummary ?? {
      noteTotal: 0,
      creatorTotal: 0,
      totalComments: 0,
    },
    pending,
    resultTotals: resultTotals ?? {
      category: 0,
      creator: 0,
      page: initialState.page,
      size: PAGE_SIZE,
      categoryHasMore: false,
      creatorHasMore: false,
      categoryTotalIsEstimate: false,
      creatorTotalIsEstimate: false,
    },
  });
  const [uiState, setUiState] = useState<SearchUiState>(() =>
    deriveUiState(
      {
        notes,
        creators,
        searchSummary: searchSummary ?? {
          noteTotal: 0,
          creatorTotal: 0,
          totalComments: 0,
        },
        pending,
        resultTotals: resultTotals ?? {
          category: 0,
          creator: 0,
          page: initialState.page,
          size: PAGE_SIZE,
          categoryHasMore: false,
          creatorHasMore: false,
          categoryTotalIsEstimate: false,
          creatorTotalIsEstimate: false,
        },
      },
      initialState.type
    )
  );
  const [isLoading, setIsLoading] = useState(false);
  const cacheRef = useRef<Map<string, SearchResultsSliceVM>>(new Map());
  const abortRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollAttemptRef = useRef(0);
  const pollStartedAtRef = useRef<number | null>(null);
  const pollJobIdRef = useRef<string | null>(null);
  const requestVersionRef = useRef(0);
  const softRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const softRefreshAttemptRef = useRef(0);
  const softRefreshStartedAtRef = useRef<number | null>(null);
  const softRefreshAbortRef = useRef<AbortController | null>(null);
  const authPromptHrefRef = useRef<string | null>(null);

  const clearPollTimer = useCallback(() => {
    if (!pollTimerRef.current) {
      return;
    }
    clearTimeout(pollTimerRef.current);
    pollTimerRef.current = null;
  }, []);

  const clearSoftRefreshTimer = useCallback(() => {
    if (!softRefreshTimerRef.current) {
      return;
    }
    clearTimeout(softRefreshTimerRef.current);
    softRefreshTimerRef.current = null;
  }, []);

  const resetPollingState = useCallback(() => {
    clearPollTimer();
    pollAttemptRef.current = 0;
    pollStartedAtRef.current = null;
    pollJobIdRef.current = null;
  }, [clearPollTimer]);

  const resetSoftRefreshState = useCallback(() => {
    clearSoftRefreshTimer();
    softRefreshAttemptRef.current = 0;
    softRefreshStartedAtRef.current = null;
    softRefreshAbortRef.current?.abort();
    softRefreshAbortRef.current = null;
  }, [clearSoftRefreshTimer]);

  const resolvePollDelayMs = useCallback((nextPollAfterMs: number | undefined, attempt: number) => {
    const defaultDelay = POLL_BACKOFF_MS[Math.min(attempt, POLL_BACKOFF_MS.length - 1)] ?? 8000;
    const upstreamDelay = Number.isFinite(nextPollAfterMs) && Number(nextPollAfterMs) > 0 ? Number(nextPollAfterMs) : 0;
    return Math.max(defaultDelay, upstreamDelay);
  }, []);

  const initialSlice = useMemo<SearchResultsSliceVM>(
    () => ({
      notes,
      creators,
      searchSummary: searchSummary ?? {
        noteTotal: 0,
        creatorTotal: 0,
        totalComments: 0,
      },
      pending,
      resultTotals: resultTotals ?? {
        category: 0,
        creator: 0,
        page: initialState.page,
        size: PAGE_SIZE,
        categoryHasMore: false,
        creatorHasMore: false,
        categoryTotalIsEstimate: false,
        creatorTotalIsEstimate: false,
      },
    }),
    [creators, initialState.page, notes, pending, resultTotals, searchSummary]
  );

  const beginRequestCycle = useCallback(() => {
    requestVersionRef.current += 1;
    resetPollingState();
    resetSoftRefreshState();
    return requestVersionRef.current;
  }, [resetPollingState, resetSoftRefreshState]);

  const applyResults = useCallback((payload: SearchResultsSliceVM, type: SearchType, version: number) => {
    if (version !== requestVersionRef.current) {
      return;
    }
    let nextPayload = payload;
    setResults((previous) => {
      nextPayload =
        previous.pending?.status === "pending" && payload.pending?.status === "pending" && getVisibleRowCount(previous, type) > 0
          ? mergeStablePayload(previous, payload, type)
          : payload;
      return nextPayload;
    });
    setUiState(deriveUiState(nextPayload, type));
  }, []);

  useEffect(() => {
    cacheRef.current.set(buildCacheKey(initialState), initialSlice);
  }, [initialSlice, initialState]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      clearPollTimer();
      resetSoftRefreshState();
    };
  }, [clearPollTimer, resetSoftRefreshState]);

  useEffect(() => {
    if (!requireAuth || authAuthenticated) {
      authPromptHrefRef.current = null;
      return;
    }
    const nextHref = buildHref(pathname, searchState);
    if (authPromptHrefRef.current === nextHref) {
      return;
    }
    authPromptHrefRef.current = nextHref;
    openAuthModal({ next: nextHref });
  }, [authAuthenticated, openAuthModal, pathname, requireAuth, searchState]);

  useEffect(() => {
    function handlePopState() {
      const nextState = parseStateFromUrl(window.location.search, initialQuery);
      const version = beginRequestCycle();
      setSearchState(nextState);
      setDraftType(nextState.type);
      const cacheKey = buildCacheKey(nextState);
      const cached = cacheRef.current.get(cacheKey);
      if (cached) {
        abortRef.current?.abort();
        setIsLoading(false);
        applyResults(cached, nextState.type, version);
        return;
      }

      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      setIsLoading(true);
      setUiState("loading");
      void fetchSearchSlice(nextState, locale, controller.signal)
        .then((payload) => {
          cacheRef.current.set(cacheKey, payload);
          applyResults(payload, nextState.type, version);
        })
        .catch((error: unknown) => {
          if ((error as Error)?.name === "AbortError") {
            return;
          }
          applyResults(
            {
              ...createEmptyResults(nextState.type, nextState.page),
              pending: { status: "failed", type: nextState.type },
            },
            nextState.type,
            version
          );
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [applyResults, beginRequestCycle, initialQuery, locale]);

  useEffect(() => {
    const currentPending = results.pending;
    if (
      !env.searchAutoPollEnabled ||
      uiState === "failed_timeout" ||
      !currentPending ||
      currentPending.status !== "pending"
    ) {
      resetPollingState();
      return;
    }

    if (currentPending.type !== searchState.type) {
      resetPollingState();
      return;
    }

    const pendingJobId = currentPending.jobId?.trim() || null;
    if (pollJobIdRef.current !== pendingJobId) {
      clearPollTimer();
      pollAttemptRef.current = 0;
      pollStartedAtRef.current = Date.now();
      pollJobIdRef.current = pendingJobId;
    }

    if (pollStartedAtRef.current == null) {
      pollStartedAtRef.current = Date.now();
    }

    const version = requestVersionRef.current;
    const waitMs = Math.max(500, resolvePollDelayMs(currentPending.nextPollAfterMs, pollAttemptRef.current));

    clearPollTimer();
    pollTimerRef.current = setTimeout(() => {
      if (version !== requestVersionRef.current) {
        return;
      }
      const startedAt = pollStartedAtRef.current ?? Date.now();
      if (Date.now() - startedAt >= SEARCH_TIMEOUT_MS) {
        resetPollingState();
        setUiState("failed_timeout");
        return;
      }
      const controller = new AbortController();
      pollAttemptRef.current += 1;
      const applyPayload = (payload: SearchResultsSliceVM) => {
        const cacheKey = buildCacheKey(searchState);
        cacheRef.current.set(cacheKey, payload);
        if (!controller.signal.aborted && version === requestVersionRef.current) {
          applyResults(payload, searchState.type, version);
          if (!payload.pending || payload.pending.status !== "pending") {
            resetPollingState();
          }
        }
      };
      const keepPendingAndRetry = (reason: string) => {
        if (!controller.signal.aborted && version === requestVersionRef.current) {
          if (Date.now() - startedAt >= SEARCH_TIMEOUT_MS) {
            resetPollingState();
            setUiState("failed_timeout");
            return;
          }
          setResults((prev) => ({
            ...prev,
            pending: {
              status: "pending",
              type: searchState.type,
              jobId: pendingJobId ?? undefined,
              pendingReason: reason,
              nextPollAfterMs: 5000,
            },
          }));
        }
      };

      if (pendingJobId) {
        void fetchSearchJobSlice({
          jobId: pendingJobId,
          state: searchState,
          locale,
          signal: controller.signal,
        })
          .then((jobPayload) => {
            if (controller.signal.aborted) {
              return;
            }
            if (!jobPayload.pending || jobPayload.pending.status !== "pending") {
              applyPayload(jobPayload);
              return;
            }

            // Job status can lag behind actual ingest completion. Probe the direct
            // search endpoint and switch to ready data as soon as DB has it.
            void fetchSearchSlice(searchState, locale, controller.signal, false)
              .then((directPayload) => {
                if (controller.signal.aborted) {
                  return;
                }
                if (!directPayload.pending || directPayload.pending.status !== "pending") {
                  applyPayload(directPayload);
                  return;
                }
                applyPayload(jobPayload);
              })
              .catch((directError: unknown) => {
                if ((directError as Error)?.name === "AbortError") {
                  return;
                }
                applyPayload(jobPayload);
              });
          })
          .catch((error: unknown) => {
            if ((error as Error)?.name === "AbortError") {
              return;
            }
            void fetchSearchSlice(searchState, locale, controller.signal, false)
              .then(applyPayload)
              .catch((fallbackError: unknown) => {
                if ((fallbackError as Error)?.name === "AbortError") {
                  return;
                }
                keepPendingAndRetry("poll_retry");
              });
          });
      } else {
        // No job id: keep polling the standard search endpoint for ready results.
        void fetchSearchSlice(searchState, locale, controller.signal, false)
          .then(applyPayload)
          .catch((error: unknown) => {
            if ((error as Error)?.name === "AbortError") {
              return;
            }
            keepPendingAndRetry("poll_retry");
          });
      }
    }, waitMs);

    return () => {
      clearPollTimer();
    };
  }, [applyResults, clearPollTimer, locale, resetPollingState, resolvePollDelayMs, results.pending, searchState, uiState]);

  const categoryRows = useMemo<CategoryRowVM[]>(() => {
    return results.notes.map((item) => {
      const like = Number(item.likeCountValue ?? parseCount(item.likeCount));
      const save = Number(item.collectionCountValue ?? parseCount(item.collectionCount));
      const comments = Number(item.commentCountValue ?? parseCount(item.commentCount));
      const stat = Number(item.interactionTotal ?? (like + save + comments));
      const read = Number(item.readCount ?? Math.round(stat * 6.2));
      return {
        id: item.noteId,
        name: item.title,
        subtitle: item.author,
        stat,
        like,
        read,
        comments,
      };
    });
  }, [results.notes]);

  const creatorRows = useMemo<CreatorRowVM[]>(() => {
    return results.creators.map((item) => ({
      id: item.authorId ?? item.name,
      name: item.name,
      followers: Number(item.followersValue ?? parseCount(item.followers)),
      notes: Number(item.notesCount ?? 0),
      sumStat: Number(item.totalInteractions ?? 0),
      direction: item.direction,
      profileUrl: item.profileUrl,
    }));
  }, [results.creators]);

  const loadState = useCallback(async (
    nextState: SearchState,
    historyMode: "push" | "replace" | "none" = "push",
    options?: {
      bypassCache?: boolean;
      forceRefresh?: boolean;
    }
  ) => {
    const version = beginRequestCycle();
    // Clear stale pending immediately so previous poll jobs cannot race and override the new search.
    setResults((prev) => (prev.pending ? { ...prev, pending: undefined } : prev));
    setSearchState(nextState);
    setUiState("loading");

    if (historyMode !== "none") {
      const href = buildHref(pathname, nextState);
      const writer = historyMode === "replace" ? window.history.replaceState : window.history.pushState;
      writer.call(window.history, null, "", href);
    }

    const bypassCache = Boolean(options?.bypassCache);
    const forceRefresh = Boolean(options?.forceRefresh);
    const cacheKey = buildCacheKey(nextState);
    const cached = !bypassCache ? cacheRef.current.get(cacheKey) : undefined;
    if (cached && hasUsableRows(cached, nextState.type)) {
      abortRef.current?.abort();
      setIsLoading(false);
      applyResults(cached, nextState.type, version);
      return;
    }

    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    setIsLoading(true);

    try {
      const payload = await fetchSearchSlice(nextState, locale, controller.signal, forceRefresh);
      cacheRef.current.set(cacheKey, payload);
      if (!controller.signal.aborted) {
        applyResults(payload, nextState.type, version);
      }
    } catch (error) {
      if ((error as Error)?.name === "AbortError") {
        return;
      }
      if (!controller.signal.aborted) {
        applyResults(
          {
            ...createEmptyResults(nextState.type, nextState.page),
            pending: { status: "failed", type: nextState.type },
          },
          nextState.type,
          version
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, [applyResults, beginRequestCycle, locale, pathname]);

  const committedType = searchState.type;
  const sortKey = searchState.sort;
  const order = searchState.order;
  const page = Math.max(1, Number(searchState.page || 1));
  const hasMoreFlag =
    committedType === "category" ? results.resultTotals?.categoryHasMore : results.resultTotals?.creatorHasMore;
  const hasMore =
    typeof hasMoreFlag === "boolean"
      ? hasMoreFlag
      : (committedType === "category" ? results.notes.length : results.creators.length) >= PAGE_SIZE;
  const visibleTotal =
    committedType === "category"
      ? Math.max(0, Number(results.resultTotals?.category ?? results.notes.length ?? 0))
      : Math.max(0, Number(results.resultTotals?.creator ?? results.creators.length ?? 0));
  const totalPages = Math.max(1, Math.ceil(visibleTotal / PAGE_SIZE), page + (hasMore ? 1 : 0));
  const pageTokens = useMemo(() => buildPageTokens(page, totalPages), [page, totalPages]);
  const visibleRows = getVisibleRowCount(results, committedType);
  const pendingStatus = results.pending?.status;

  useEffect(() => {
    if (
      !env.searchAutoPollEnabled ||
      uiState !== "ready" ||
      pendingStatus === "pending" ||
      visibleRows === 0 ||
      visibleRows >= PAGE_SIZE ||
      hasMore
    ) {
      resetSoftRefreshState();
      return;
    }

    if (softRefreshStartedAtRef.current == null) {
      softRefreshStartedAtRef.current = Date.now();
    }

    const version = requestVersionRef.current;
    const waitMs =
      SOFT_REFRESH_BACKOFF_MS[Math.min(softRefreshAttemptRef.current, SOFT_REFRESH_BACKOFF_MS.length - 1)] ?? 8000;

    clearSoftRefreshTimer();
    softRefreshTimerRef.current = setTimeout(() => {
      if (version !== requestVersionRef.current) {
        return;
      }
      const startedAt = softRefreshStartedAtRef.current ?? Date.now();
      if (Date.now() - startedAt >= SEARCH_TIMEOUT_MS) {
        resetSoftRefreshState();
        return;
      }

      const controller = new AbortController();
      softRefreshAbortRef.current?.abort();
      softRefreshAbortRef.current = controller;
      softRefreshAttemptRef.current += 1;

      void fetchSearchSlice(searchState, locale, controller.signal, false)
        .then((payload) => {
          if (controller.signal.aborted || version !== requestVersionRef.current) {
            return;
          }
          const cacheKey = buildCacheKey(searchState);
          cacheRef.current.set(cacheKey, payload);
          applyResults(payload, searchState.type, version);
        })
        .catch((error: unknown) => {
          if ((error as Error)?.name === "AbortError") {
            return;
          }
        });
    }, waitMs);

    return () => {
      clearSoftRefreshTimer();
    };
  }, [
    applyResults,
    clearSoftRefreshTimer,
    hasMore,
    locale,
    pendingStatus,
    resetSoftRefreshState,
    searchState,
    uiState,
    visibleRows,
  ]);

  const labels = useMemo(() => buildXhsSearchLabels(locale), [locale]);
  const canSearchInPage = authenticated || authAuthenticated || !requireAuth;
  const showSkeleton = visibleRows === 0 && (uiState === "loading" || uiState === "pending");
  const showTimeoutPrompt = visibleRows === 0 && uiState === "failed_timeout";

  function requireAuthFor(nextState: SearchState) {
    const nextHref = buildHref(pathname, nextState);
    authPromptHrefRef.current = nextHref;
    openAuthModal({ next: nextHref });
  }

  function onTypeChange(type: SearchType) {
    setDraftType(type);
  }

  function onSearch(nextQuery: string) {
    const trimmed = nextQuery.trim() || searchState.q || initialQuery;
    const nextState: SearchState = {
      type: draftType,
      q: trimmed,
      sort: draftType === "creator" ? "relevance" : "stat",
      order: "desc",
      page: 1,
      // New manual searches should not be constrained by stale industry filters
      // carried from previous card-driven navigation.
      industry: undefined,
    };

    if (!canSearchInPage) {
      requireAuthFor(nextState);
      return;
    }

    const queryChanged = nextState.q !== searchState.q || nextState.type !== searchState.type;
    const currentTotal =
      committedType === "category"
        ? (results.resultTotals?.category ?? results.notes.length)
        : (results.resultTotals?.creator ?? results.creators.length);
    // Keep local cache as default. Only when user re-submits the same query and
    // current result appears capped at one page do we force backend refresh.
    const shouldForceBackfill = !queryChanged && !results.pending && currentTotal <= PAGE_SIZE && !hasMore;
    void loadState(nextState, "push", {
      bypassCache: queryChanged || shouldForceBackfill,
      forceRefresh: shouldForceBackfill,
    });
  }

  function onRetryCurrentSearch() {
    void loadState(searchState, "replace", {
      bypassCache: true,
      forceRefresh: true,
    });
  }

  function onSortChange(nextSort: SortKey) {
    if (
      (committedType === "category" && !isCategorySortKey(nextSort)) ||
      (committedType === "creator" && !isCreatorSortKey(nextSort))
    ) {
      return;
    }

    const nextState: SearchState = {
      ...searchState,
      sort: nextSort,
      order: searchState.sort === nextSort && searchState.order === "desc" ? "asc" : "desc",
      page: 1,
    };

    if (!canSearchInPage) {
      requireAuthFor(nextState);
      return;
    }

    // Sorting must bypass cache to avoid showing stale order from previous requests.
    void loadState(nextState, "push", { bypassCache: true, forceRefresh: false });
  }

  function onPageChange(nextPage: number) {
    const safePage = Math.max(1, nextPage);
    if (safePage === searchState.page) {
      return;
    }
    if (safePage > totalPages) {
      return;
    }
    const nextState = { ...searchState, page: safePage };
    if (!canSearchInPage) {
      requireAuthFor(nextState);
      return;
    }
    void loadState(nextState);
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
    <XhsSearchFrame
      backHref={`/${locale}/datacenter/xhs`}
      locale={locale}
      onSearch={onSearch}
      onTypeChange={onTypeChange}
      searchBarLoading={isLoading}
      searchQuery={searchState.q}
      selectedType={draftType}
    >
      {showSkeleton ? (
        <XhsSearchPanelsSkeleton activeType={committedType} locale={locale} message={labels.loadingResults} />
      ) : showTimeoutPrompt ? (
        <section className="rounded-xl border border-slate-100 bg-white px-6 py-8 text-center shadow-sm">
          <div className="mx-auto max-w-md">
            <div className="text-sm text-slate-500">{labels.loadingTimeout}</div>
            <button
              className="mt-4 inline-flex h-10 items-center justify-center rounded-lg border border-peach-200 bg-peach-50 px-4 text-sm font-medium text-peach-600 transition hover:border-peach-300 hover:bg-peach-100"
              onClick={onRetryCurrentSearch}
              type="button"
            >
              {labels.retrySearch}
            </button>
          </div>
        </section>
      ) : (
        <>
      <section className="rounded-xl border border-slate-100 bg-white shadow-sm">
        <div className="overflow-x-auto">
          {committedType === "category" ? (
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
                {categoryRows.map((item, index) => (
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
                {creatorRows.map((item, index) => (
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
                      {item.profileUrl ? (
                        <Link
                          className="text-sm text-peach-500 transition hover:text-peach-600"
                          href={item.profileUrl}
                          rel="noreferrer"
                          target="_blank"
                        >
                          {labels.creatorHome}
                        </Link>
                      ) : (
                        <span className="text-sm text-slate-400">-</span>
                      )}
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
          disabled={page <= 1 || isLoading}
          onClick={() => onPageChange(page - 1)}
          type="button"
        >
          {"<"}
        </button>
        {pageTokens.map((token, index) =>
          token === "..." ? (
            <span
              className="h-9 min-w-[32px] px-1 py-2 text-center text-sm text-slate-400"
              key={`ellipsis-${index}`}
            >
              ...
            </span>
          ) : (
            <button
              className={`h-9 min-w-[40px] rounded-lg border px-3 text-sm transition ${
                token === page
                  ? "border-peach-200 bg-peach-50 font-medium text-peach-600"
                  : "border-slate-200 text-slate-500 hover:border-peach-500/35 hover:text-peach-500"
              }`}
              disabled={isLoading}
              key={`page-${token}`}
              onClick={() => onPageChange(token)}
              type="button"
            >
              {token}
            </button>
          )
        )}
        <button
          className="h-9 rounded-lg border border-slate-200 px-3 text-sm text-slate-500 transition hover:border-peach-500/35 hover:text-peach-500"
          disabled={page >= totalPages || isLoading}
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
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">
              {toNumberLabel(results.searchSummary.noteTotal, locale)}
            </div>
          </article>
          <article className="rounded-lg border border-slate-100 bg-white px-3 py-2">
            <div className="text-[11px] text-slate-500">{labels.summaryCreators}</div>
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">
              {toNumberLabel(results.searchSummary.creatorTotal, locale)}
            </div>
          </article>
          <article className="rounded-lg border border-slate-100 bg-white px-3 py-2">
            <div className="text-[11px] text-slate-500">{labels.summaryComments}</div>
            <div className="mt-1 text-sm font-medium text-slate-800 tabular-nums">
              {toNumberLabel(results.searchSummary.totalComments, locale)}
            </div>
          </article>
        </div>
      </section>
        </>
      )}
    </XhsSearchFrame>
  );
}
