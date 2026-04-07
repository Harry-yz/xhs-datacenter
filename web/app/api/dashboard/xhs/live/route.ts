import { NextResponse } from "next/server";

import { env } from "@/config/env";

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type LiveApiData = {
  new_notes_24h?: number;
  updated_notes_30m?: number;
  new_comments_30m?: number;
  jobs_running?: number;
  generated_at?: string;
};

export async function GET() {
  try {
    const response = await fetch(`${env.internalApiBaseUrl}/dashboard/xhs/live`, {
      cache: "no-store"
    });

    if (!response.ok) {
      return NextResponse.json({ message: "upstream failed" }, { status: 502 });
    }

    const payload = (await response.json()) as ApiEnvelope<LiveApiData>;
    return NextResponse.json(
      {
        newNotes24h: Number(payload.data?.new_notes_24h ?? 0),
        updatedNotes30m: Number(payload.data?.updated_notes_30m ?? 0),
        newComments30m: Number(payload.data?.new_comments_30m ?? 0),
        jobsRunning: Number(payload.data?.jobs_running ?? 0),
        generatedAt: String(payload.data?.generated_at ?? "")
      },
      { status: 200 }
    );
  } catch {
    return NextResponse.json({ message: "upstream unavailable" }, { status: 502 });
  }
}
