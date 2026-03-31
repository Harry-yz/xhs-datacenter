import { type Locale } from "@/config/i18n";

export function withLocale(locale: Locale, path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `/${locale}${normalized}`;
}

export function isProtectedPath(pathname: string) {
  return ["/datacenter/xhs/search", "/datacenter/xhs/category/", "/datacenter/xhs/brand/", "/datacenter/xhs/note/"].some(
    (prefix) => pathname.includes(prefix)
  );
}
