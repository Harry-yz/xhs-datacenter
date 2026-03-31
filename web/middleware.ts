import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { DEFAULT_LOCALE, LOCALE_COOKIE, SUPPORTED_LOCALES, isLocale } from "@/config/i18n";

const PUBLIC_FILE = /\.(.*)$/;
const CATEGORY_QUERY_BY_SLUG: Record<string, { zh: string; en: string }> = {
  sunscreen: { zh: "防晒", en: "Sunscreen" },
  beauty: { zh: "美妆", en: "Beauty" },
  "mother-baby": { zh: "母婴", en: "Mother & Baby" },
  fashion: { zh: "时尚", en: "Fashion" },
  food: { zh: "美食", en: "Food" },
  travel: { zh: "旅行", en: "Travel" },
  home: { zh: "家居", en: "Home" },
  digital: { zh: "数码", en: "Digital" },
  fitness: { zh: "运动", en: "Fitness" },
  pets: { zh: "宠物", en: "Pets" },
  education: { zh: "教育", en: "Education" },
  automotive: { zh: "汽车", en: "Automotive" },
  luxury: { zh: "奢品", en: "Luxury" }
};

function safeDecode(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function getAbsoluteUrl(request: NextRequest, pathWithQuery: string) {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = (forwardedHost ?? request.headers.get("host") ?? request.nextUrl.host).split(",")[0]?.trim();
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const protocol = (forwardedProto ?? request.nextUrl.protocol.replace(":", "")).split(",")[0]?.trim() || "http";
  return new URL(pathWithQuery, `${protocol}://${host}`);
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/favicon") ||
    pathname.startsWith("/images") ||
    PUBLIC_FILE.test(pathname)
  ) {
    return NextResponse.next();
  }

  const hasLocale = SUPPORTED_LOCALES.some((locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`));

  if (!hasLocale) {
    const locale = request.cookies.get(LOCALE_COOKIE)?.value ?? DEFAULT_LOCALE;
    const redirectPath = `/${locale}${pathname}${search}`;
    const response = NextResponse.redirect(getAbsoluteUrl(request, redirectPath));
    response.cookies.set(LOCALE_COOKIE, locale);
    return response;
  }

  const localeToken = pathname.split("/")[1];
  const locale = isLocale(localeToken) ? localeToken : DEFAULT_LOCALE;

  const legacyCategoryPrefix = `/${locale}/datacenter/xhs/category/`;
  if (pathname.startsWith(legacyCategoryPrefix)) {
    const slug = pathname.slice(legacyCategoryPrefix.length).split("/")[0] ?? "";
    if (slug) {
      const decodedSlug = safeDecode(slug);
      const normalizedSlug = decodedSlug.toLowerCase();
      const mappedQuery =
        CATEGORY_QUERY_BY_SLUG[normalizedSlug]?.[locale] ?? decodedSlug.replace(/-/g, " ");
      const redirectPath = `/${locale}/datacenter/xhs/search?type=category&q=${encodeURIComponent(mappedQuery)}`;
      return NextResponse.redirect(getAbsoluteUrl(request, redirectPath), 301);
    }
  }

  const response = NextResponse.next();
  response.cookies.set(LOCALE_COOKIE, locale);
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"]
};
