import type { Metadata } from "next";
import { cookies } from "next/headers";

import { XhsSearchResultsView } from "@/components/datacenter/xhs-search-results-view";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { SESSION_COOKIE } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";
import { PageShell } from "@/layouts/page-shell";
import { getSearchWorkbench } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../../../layout";

export async function generateMetadata({ params }: AppPageProps): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(dictionary.xhs.searchWorkbench, "Query-based Xiaohongshu data workbench with BI views and AI strategy blocks.");
}

export default async function SearchWorkbenchPage({ params, searchParams }: AppPageProps) {
  const isZh = params.lang === "zh";
  const query = typeof searchParams?.q === "string" && searchParams.q.trim() ? searchParams.q.trim() : isZh ? "防晒" : "sunscreen";
  const dictionary = await getDictionary(params.lang);
  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);
  // Auth gate is intentionally preserved: unauthenticated users must log in before viewing real search results.
  const workbench = authenticated
    ? await getSearchWorkbench(params.lang, searchParams as Record<string, string> | undefined)
    : {
        notes: [],
        creators: [],
        searchSummary: {
          noteTotal: 0,
          creatorTotal: 0,
          totalComments: 0,
        },
        resultTotals: {
          category: 0,
          creator: 0,
          page: 1,
          size: 30,
          categoryHasMore: false,
          creatorHasMore: false,
        },
        pending: undefined,
      };

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={params.lang}
        pathname={withLocale(params.lang, "/datacenter/xhs/search")}
      />

      <main className="mx-auto max-w-8xl px-4 pb-16 pt-6 md:px-8 md:pb-24">
        <XhsSearchResultsView
          authenticated={authenticated}
          creators={workbench.creators}
          initialQuery={query}
          initialParams={searchParams as Record<string, string> | undefined}
          locale={params.lang}
          notes={workbench.notes}
          pending={workbench.pending}
          requireAuth={!authenticated}
          resultTotals={workbench.resultTotals}
          searchSummary={workbench.searchSummary}
        />
      </main>
    </PageShell>
  );
}
