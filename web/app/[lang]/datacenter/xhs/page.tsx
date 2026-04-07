import type { Metadata } from "next";
import { cookies } from "next/headers";

import { DashboardHero } from "@/components/datacenter/dashboard-hero";
import { LiveIndustryMatrix } from "@/components/datacenter/live-industry-matrix";
import { LiveKpiPanel } from "@/components/datacenter/live-kpi-panel";
import { PureTrendChart } from "@/components/datacenter/pure-trend-chart";
import { SectionHeading } from "@/components/datacenter/section-heading";
import { XhsSearchEntry } from "@/components/datacenter/xhs-search-entry";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { SESSION_COOKIE } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";
import { PageShell } from "@/layouts/page-shell";
import { getXhsOverview } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../../layout";

export async function generateMetadata({ params }: AppPageProps): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(dictionary.xhs.overview, "Xiaohongshu BI dashboard and AI marketing decision center.");
}

export default async function XhsOverviewPage({ params }: AppPageProps) {
  const isZh = params.lang === "zh";
  const [dictionary, overview] = await Promise.all([
    getDictionary(params.lang),
    getXhsOverview(params.lang)
  ]);
  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);
  const fallbackKpis = overview.kpis.slice(0, 3);
  const searchBasePath = withLocale(params.lang, "/datacenter/xhs/search");

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={params.lang}
        pathname={withLocale(params.lang, "/datacenter/xhs")}
      />

      <main className="mx-auto max-w-8xl space-y-4 px-4 pb-16 pt-3 md:px-8 md:space-y-4 md:pb-24 md:pt-4">
        <XhsSearchEntry
          authenticated={authenticated}
          backHref={withLocale(params.lang, "/datacenter")}
          locale={params.lang}
          searchPath={withLocale(params.lang, "/datacenter/xhs/search")}
        />

        <DashboardHero
          compact
          description={isZh ? "聚焦小红书核心盘面，先看总量再看趋势。" : "Focus on core Xiaohongshu metrics before diving into trends."}
          eyebrow={dictionary.navigation.xhsLabel}
          rightSlot={
            <LiveKpiPanel fallbackKpis={fallbackKpis} initialTotals={null} locale={params.lang} />
          }
          title={dictionary.common.dataCenter}
        />

        <section>
          <PureTrendChart data={overview.trendExplorer.windows} locale={isZh ? "zh" : "en"} />
        </section>

        <section>
          <SectionHeading
            eyebrow={isZh ? "行业矩阵" : "Industry Matrix"}
            title={isZh ? "行业入口" : "Industry Entrances"}
          />
          <LiveIndustryMatrix
            authenticated={authenticated}
            initialIndustries={overview.industries}
            locale={params.lang}
            searchBasePath={searchBasePath}
          />
        </section>
      </main>
    </PageShell>
  );
}
