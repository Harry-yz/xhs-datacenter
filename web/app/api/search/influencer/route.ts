import { NextRequest, NextResponse } from "next/server";

import { env } from "@/config/env";
import { buildSearchResultsSlice } from "@/lib/search-workbench";
import { type Locale } from "@/config/i18n";

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type RequestBody = {
  locale?: Locale;
  query: string;
  industry?: string;
  sort?: "relevance" | "followers" | "notes" | "sumStat";
  order?: "asc" | "desc";
  page?: number;
  size?: number;
  date_range?: 7 | 30 | 90;
  freshness_hours?: number;
  force_refresh?: boolean;
  include_notes?: boolean;
};

export const dynamic = "force-dynamic";
export const revalidate = 0;
const UPSTREAM_TIMEOUT_MS = 15000;
const CREATOR_SORT_KEYS = ["relevance", "followers", "notes", "sumStat"] as const;
const ORDER_KEYS = ["asc", "desc"] as const;

function isCreatorSortKey(value: string): value is (typeof CREATOR_SORT_KEYS)[number] {
  return (CREATOR_SORT_KEYS as readonly string[]).includes(value);
}

function isOrderKey(value: string): value is (typeof ORDER_KEYS)[number] {
  return (ORDER_KEYS as readonly string[]).includes(value);
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
    const sort = isCreatorSortKey(rawSort) ? rawSort : "relevance";
    const order = isOrderKey(rawOrder) ? rawOrder : "desc";
    if (rawSort && !isCreatorSortKey(rawSort)) {
      console.warn("[search-api] creator invalid sort fallback", { query, rawSort, fallbackSort: sort });
    }
    if (rawOrder && !isOrderKey(rawOrder)) {
      console.warn("[search-api] creator invalid order fallback", { query, rawOrder, fallbackOrder: order });
    }

    const upstream = await fetch(`${env.internalApiBaseUrl}/search/influencer`, {
      method: "POST",
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: body.query,
        industry: body.industry,
        sort,
        order,
        page,
        size,
        date_range: body.date_range ?? 30,
        freshness_hours: body.freshness_hours ?? 24,
        force_refresh: Boolean(body.force_refresh),
        include_notes: Boolean(body.include_notes),
      }),
    });

    if (!upstream.ok) {
      const classified = classifyUpstreamResponse(upstream);
      console.error("[search-api] influencer upstream non-2xx", {
        type: "creator",
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
    const pagination =
      payload.data && typeof payload.data === "object"
        ? ((payload.data as Record<string, unknown>).pagination as Record<string, unknown> | undefined)
        : undefined;
    const hasMore = Boolean(pagination?.has_more);
    const slice = buildSearchResultsSlice({
      locale,
      activeType: "creator",
      payload: payload.data ?? {},
      page,
      size,
    });
    slice.resultTotals = {
      ...slice.resultTotals,
      categoryHasMore: false,
      creatorHasMore: hasMore,
    };
    console.info("[search-api] creator response snapshot", {
      query,
      type: "creator",
      sort,
      order,
      page,
      total: slice.resultTotals?.creator ?? 0,
      firstAuthorId: slice.creators[0]?.authorId ?? null,
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
    console.error("[search-api] influencer upstream error", {
      type: "creator",
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
