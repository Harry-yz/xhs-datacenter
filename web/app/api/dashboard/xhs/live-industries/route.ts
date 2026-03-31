import { NextResponse } from "next/server";

import { env } from "@/config/env";

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type LiveIndustryItem = {
  industry_key?: string;
  industry_name?: string;
  note_count?: number;
};

type LiveIndustriesApiData = {
  items?: LiveIndustryItem[];
  generated_at?: string;
};

export async function GET() {
  try {
    const response = await fetch(`${env.apiBaseUrl}/dashboard/xhs/live-industries`, {
      cache: "no-store"
    });

    if (!response.ok) {
      return NextResponse.json({ message: "upstream failed" }, { status: 502 });
    }

    const payload = (await response.json()) as ApiEnvelope<LiveIndustriesApiData>;
    const items = Array.isArray(payload.data?.items) ? payload.data.items : [];

    return NextResponse.json(
      {
        items: items.map((item) => ({
          industryKey: String(item.industry_key ?? ""),
          industryName: String(item.industry_name ?? ""),
          noteCount: Number(item.note_count ?? 0)
        })),
        generatedAt: String(payload.data?.generated_at ?? "")
      },
      { status: 200 }
    );
  } catch {
    return NextResponse.json({ message: "upstream unavailable" }, { status: 502 });
  }
}
