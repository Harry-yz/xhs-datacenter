import { NextRequest, NextResponse } from "next/server";

import { DEFAULT_LOCALE, SESSION_COOKIE } from "@/config/i18n";

function getRequestOrigin(request: NextRequest) {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = (forwardedHost ?? request.headers.get("host") ?? "localhost:3210").split(",")[0]?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const protocol = (forwardedProto ?? "http").split(",")[0]?.trim() || "http";
  return `${protocol}://${host}`;
}

export async function POST(request: NextRequest) {
  const referer = request.headers.get("referer");
  let nextPath = `/${DEFAULT_LOCALE}/datacenter`;
  if (referer) {
    try {
      const parsed = new URL(referer);
      nextPath = `${parsed.pathname}${parsed.search}`;
    } catch {
      nextPath = `/${DEFAULT_LOCALE}/datacenter`;
    }
  }
  const response = NextResponse.redirect(new URL(nextPath, getRequestOrigin(request)));
  response.cookies.delete(SESSION_COOKIE);
  return response;
}
