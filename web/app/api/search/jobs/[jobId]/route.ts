import { NextRequest, NextResponse } from "next/server";

import { env } from "@/config/env";
import { type Locale } from "@/config/i18n";
import { buildSearchResultsSlice } from "@/lib/search-workbench";

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

export const dynamic = "force-dynamic";
export const revalidate = 0;
const UPSTREAM_TIMEOUT_MS = 30000;

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

function resolveType(rawType: string, payload: Record<string, unknown>): "category" | "creator" {
  if (rawType === "creator" || rawType === "category") {
    return rawType;
  }
  return String(payload.search_type ?? "") === "influencer" ? "creator" : "category";
}

export async function GET(request: NextRequest, context: { params: { jobId: string } }) {
  const startedAt = Date.now();
  const locale = request.nextUrl.searchParams.get("locale") === "en" ? "en" : "zh";
  const page = Math.max(1, Number(request.nextUrl.searchParams.get("page") ?? 1));
  const size = Math.max(1, Number(request.nextUrl.searchParams.get("size") ?? 30));
  const explicitType = String(request.nextUrl.searchParams.get("type") ?? "");
  const jobId = String(context.params.jobId ?? "").trim();

  if (!jobId) {
    return NextResponse.json({ message: "invalid job id" }, { status: 400 });
  }

  try {
    const upstream = await fetch(
      `${env.internalApiBaseUrl}/search/jobs/${encodeURIComponent(jobId)}?page=${page}&size=${size}`,
      {
        method: "GET",
        cache: "no-store",
        redirect: "manual",
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      }
    );

    if (!upstream.ok) {
      const classified = classifyUpstreamResponse(upstream);
      console.error("[search-api] job polling upstream non-2xx", {
        jobId,
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
    const data = payload.data ?? {};
    const activeType = resolveType(explicitType, data);
    const slice = buildSearchResultsSlice({
      locale: locale as Locale,
      activeType,
      payload: data,
      page,
      size,
    });

    return NextResponse.json(slice, {
      status: 200,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      },
    });
  } catch (error) {
    const details = classifyUpstreamError(error);
    console.error("[search-api] job polling upstream error", {
      jobId,
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
