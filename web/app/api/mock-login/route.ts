import { NextRequest, NextResponse } from "next/server";

import { DEFAULT_LOCALE, LOCALE_COOKIE, SESSION_COOKIE } from "@/config/i18n";

function getRequestOrigin(request: NextRequest) {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = (forwardedHost ?? request.headers.get("host") ?? "localhost:3210").split(",")[0]?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const protocol = (forwardedProto ?? "http").split(",")[0]?.trim() || "http";
  return `${protocol}://${host}`;
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const rawNext = String(formData.get("next") || `/${DEFAULT_LOCALE}/datacenter/xhs`);
  const next = rawNext.startsWith("/") ? rawNext : `/${DEFAULT_LOCALE}/datacenter/xhs`;
  const locale = request.cookies.get(LOCALE_COOKIE)?.value ?? DEFAULT_LOCALE;

  const response = NextResponse.redirect(new URL(next, getRequestOrigin(request)));
  response.cookies.set(SESSION_COOKIE, "demo", { httpOnly: true, path: "/" });
  response.cookies.set(LOCALE_COOKIE, locale, { path: "/" });
  return response;
}
