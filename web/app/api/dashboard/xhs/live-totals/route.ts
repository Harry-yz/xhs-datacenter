import { NextResponse } from "next/server";

import { env } from "@/config/env";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type LiveTotalsApiData = {
  notes_total?: number;
  creators_total?: number;
  comments_total?: number;
  generated_at?: string;
};

export async function GET() {
  try {
    const response = await fetch(`${env.internalApiBaseUrl}/dashboard/xhs/live-totals`, {
      cache: "no-store",
      signal: AbortSignal.timeout(8000)
    });

    if (!response.ok) {
      return NextResponse.json({ message: "upstream failed" }, { status: 502 });
    }

    const payload = (await response.json()) as ApiEnvelope<LiveTotalsApiData>;
    return NextResponse.json(
      {
        notesTotal: Number(payload.data?.notes_total ?? 0),
        creatorsTotal: Number(payload.data?.creators_total ?? 0),
        commentsTotal: Number(payload.data?.comments_total ?? 0),
        generatedAt: String(payload.data?.generated_at ?? "")
      },
      {
        status: 200,
        headers: {
          "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"
        }
      }
    );
  } catch {
    return NextResponse.json({ message: "upstream unavailable" }, { status: 502 });
  }
}
