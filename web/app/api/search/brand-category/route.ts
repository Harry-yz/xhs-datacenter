import { NextRequest, NextResponse } from "next/server";

import { env } from "@/config/env";
import { type Locale } from "@/config/i18n";
import { buildSearchResultsSlice } from "@/lib/search-workbench";

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type RequestBody = {
  locale?: Locale;
  query: string;
  mode?: "brand" | "category";
  industry?: string;
  sort?: "stat" | "like" | "read" | "comments";
  order?: "asc" | "desc";
  page?: number;
  size?: number;
  min_like?: number;
  date_range?: 7 | 30 | 90;
  freshness_hours?: number;
  force_refresh?: boolean;
};

export const dynamic = "force-dynamic";
export const revalidate = 0;
const UPSTREAM_TIMEOUT_MS = 30000;
const CATEGORY_SORT_KEYS = ["stat", "like", "read", "comments"] as const;
const ORDER_KEYS = ["asc", "desc"] as const;
const MODE_KEYS = ["brand", "category"] as const;

function isCategorySortKey(value: string): value is (typeof CATEGORY_SORT_KEYS)[number] {
  return (CATEGORY_SORT_KEYS as readonly string[]).includes(value);
}

function isOrderKey(value: string): value is (typeof ORDER_KEYS)[number] {
  return (ORDER_KEYS as readonly string[]).includes(value);
}

function isModeKey(value: string): value is (typeof MODE_KEYS)[number] {
  return (MODE_KEYS as readonly string[]).includes(value);
}

function classifyUpstreamError(error: unknown) {
  const name = error && typeof error === "object" && "name" in error ? String((error as { name?: unknown }).name ?? "") : "";
  const message = error instanceof Error ? error.message : String(error ?? "");
  const timeout = name === "AbortError" || name === "TimeoutError" || /timeout|timed out|abort/i.test(message);
  if (timeout) {
    return { errorType: "upstream_timeout", status: 504, name, message };
  }
  return { errorType: "upstream_error", status: 502, name, message };
}

function classifyUpstreamResponse(response: Response) {
  const location = response.headers.get("location");
  const redirectedMisconfigured =
    response.redirected || response.type === "opaqueredirect" || Boolean(location) || (response.status >= 300 && response.status < 400);
  if (redirectedMisconfigured || response.status === 405) {
    return { errorType: "upstream_misconfigured", status: 502 };
  }
  return { errorType: "upstream_error", status: 502 };
}

function toObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

export async function POST(request: NextRequest) {
  const startedAt = Date.now();
  let query = "";
  let page = 1;
  let size = 30;

  try {
    const body = (await request.json()) as RequestBody;
    query = String(body.query ?? "");
    const locale = body.locale === "en" ? "en" : "zh";
    page = Math.max(1, Number(body.page ?? 1));
    size = Math.max(1, Number(body.size ?? 30));
    const rawSort = String(body.sort ?? "").trim();
    const rawOrder = String(body.order ?? "").trim();
    const rawMode = String(body.mode ?? "").trim();
    const sort = isCategorySortKey(rawSort) ? rawSort : "stat";
    const order = isOrderKey(rawOrder) ? rawOrder : "desc";
    const mode = isModeKey(rawMode) ? rawMode : "category";
    if (rawSort && !isCategorySortKey(rawSort)) {
      console.warn("[search-api] category invalid sort fallback", { query, rawSort, fallbackSort: sort });
    }
    if (rawOrder && !isOrderKey(rawOrder)) {
      console.warn("[search-api] category invalid order fallback", { query, rawOrder, fallbackOrder: order });
    }
    if (rawMode && !isModeKey(rawMode)) {
      console.warn("[search-api] category invalid mode fallback", { query, rawMode, fallbackMode: mode });
    }

    const upstream = await fetch(`${env.internalApiBaseUrl}/search/brand-category`, {
      method: "POST",
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: body.query,
        mode,
        industry: body.industry,
        min_like: Math.max(0, Number(body.min_like ?? 1)),
        sort,
        order,
        page,
        size,
        date_range: body.date_range ?? 30,
        freshness_hours: body.freshness_hours ?? 24,
        force_refresh: Boolean(body.force_refresh),
      }),
    });

    if (!upstream.ok) {
      const classified = classifyUpstreamResponse(upstream);
      console.error("[search-api] category upstream non-2xx", {
        type: "category",
        query,
        page,
        size,
        upstreamStatus: upstream.status,
        upstreamLocation: upstream.headers.get("location"),
        redirected: upstream.redirected,
        errorType: classified.errorType,
        durationMs: Date.now() - startedAt,
      });
      return NextResponse.json(
        { message: "upstream failed", errorType: classified.errorType, upstreamStatus: upstream.status },
        { status: classified.status }
      );
    }

    const payload = (await upstream.json()) as ApiEnvelope<Record<string, unknown>>;
    const data = toObject(payload.data);
    const pagination = toObject(data.pagination);
    const hasMore = Boolean(pagination?.has_more);
    const slice = buildSearchResultsSlice({
      locale,
      activeType: "category",
      payload: data,
      page,
      size,
    });
    slice.resultTotals = {
      ...slice.resultTotals,
      categoryHasMore: hasMore,
      creatorHasMore: false,
    };
    console.info("[search-api] category response snapshot", {
      query,
      type: "category",
      mode,
      sort,
      order,
      page,
      total: slice.resultTotals?.category ?? 0,
      firstNoteId: slice.notes[0]?.noteId ?? null,
      pending: slice.pending?.status ?? null,
      durationMs: Date.now() - startedAt,
    });

    return NextResponse.json(slice, {
      status: 200,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      },
    });
  } catch (error) {
    const details = classifyUpstreamError(error);
    console.error("[search-api] category upstream error", {
      type: "category",
      query,
      page,
      size,
      errorType: details.errorType,
      errorName: details.name,
      errorMessage: details.message,
      durationMs: Date.now() - startedAt,
    });
    return NextResponse.json(
      { message: "upstream unavailable", errorType: details.errorType },
      { status: details.status }
    );
  }
}
