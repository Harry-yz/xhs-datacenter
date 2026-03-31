import { NextResponse } from "next/server";

import { env } from "@/config/env";

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
    const response = await fetch(`${env.apiBaseUrl}/dashboard/xhs/live-totals`, {
      cache: "no-store"
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
      { status: 200 }
    );
  } catch {
    return NextResponse.json({ message: "upstream unavailable" }, { status: 502 });
  }
}
