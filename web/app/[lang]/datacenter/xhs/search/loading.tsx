import { cookies } from "next/headers";

import { XhsSearchLoadingView } from "@/components/datacenter/xhs-search-loading-view";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { isAuthenticatedSession } from "@/config/auth";
import { DEFAULT_LOCALE, LOCALE_COOKIE, SESSION_COOKIE, isLocale } from "@/config/i18n";
import { PageShell } from "@/layouts/page-shell";
import { withLocale } from "@/utils/routes";

export default async function SearchWorkbenchLoading() {
  const cookieStore = cookies();
  const localeCookie = cookieStore.get(LOCALE_COOKIE)?.value ?? DEFAULT_LOCALE;
  const locale = isLocale(localeCookie) ? localeCookie : DEFAULT_LOCALE;
  const dictionary = await getDictionary(locale);
  const authenticated = isAuthenticatedSession(cookieStore.get(SESSION_COOKIE)?.value);

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={locale}
        pathname={withLocale(locale, "/datacenter/xhs/search")}
      />

      <main className="mx-auto max-w-8xl px-4 pb-16 pt-6 md:px-8 md:pb-24">
        <XhsSearchLoadingView />
      </main>
    </PageShell>
  );
}
