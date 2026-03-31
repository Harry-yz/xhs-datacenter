import type { Metadata } from "next";
import { cookies } from "next/headers";

import { BrandRankingPanel } from "@/components/datacenter/brand-ranking-panel";
import { DashboardHero } from "@/components/datacenter/dashboard-hero";
import { FilterChipBar } from "@/components/datacenter/filter-chip-bar";
import { InsightBlock } from "@/components/datacenter/insight-block";
import { MetricCard } from "@/components/datacenter/metric-card";
import { MiniAreaChart } from "@/components/datacenter/mini-area-chart";
import { NoteAnalysisCard } from "@/components/datacenter/note-analysis-card";
import { PageToolbar } from "@/components/datacenter/page-toolbar";
import { SectionHeading } from "@/components/datacenter/section-heading";
import { StatusOverviewStrip } from "@/components/datacenter/status-overview-strip";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { SESSION_COOKIE } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";
import { PageShell } from "@/layouts/page-shell";
import { getCategoryDetail } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../../../../layout";

export async function generateMetadata({
  params
}: AppPageProps & { params: { lang: "zh" | "en"; slug: string } }): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(`${dictionary.xhs.categoryOpportunity} · ${params.slug}`, "Category opportunity dashboard with BI views and AI marketing summaries.");
}

export default async function CategoryDetailPage({ params }: AppPageProps & { params: { lang: "zh" | "en"; slug: string } }) {
  const isZh = params.lang === "zh";
  const [dictionary, detail] = await Promise.all([getDictionary(params.lang), getCategoryDetail(params.lang, params.slug)]);
  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={params.lang}
        pathname={withLocale(params.lang, `/datacenter/xhs/category/${params.slug}`)}
      />

      <main className="mx-auto max-w-8xl space-y-8 px-4 pb-16 pt-8 md:px-8 md:space-y-10 md:pb-24">
        <PageToolbar backHref={withLocale(params.lang, "/datacenter/xhs")} backLabel={isZh ? "返回小红书" : "Back"} />

        <DashboardHero
          breadcrumb={detail.breadcrumb.join(" / ")}
          description={detail.heroSummary}
          rightSlot={
            <div className="grid gap-4 md:grid-cols-3">
              {detail.kpis.map((item) => (
                <MetricCard item={item} key={item.label} />
              ))}
            </div>
          }
          title={dictionary.common.dataCenter}
        />

        <FilterChipBar items={detail.filters} />
        <StatusOverviewStrip items={detail.statusStats} />

        <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <MiniAreaChart items={detail.trend} eyebrow={isZh ? "趋势" : "Trend"} title={isZh ? "品类走势" : "Category Trend"} periodLabel={isZh ? "7天" : "7D"} />
          <div className="grid gap-6">
            {detail.opportunityCards.map((item) => (
              <InsightBlock key={item.title} items={[item.value, item.description]} title={item.title} />
            ))}
          </div>
        </section>

        <section>
          <SectionHeading eyebrow={isZh ? "用户需求层" : "Need Layers"} title={isZh ? "痛点、卖点、场景" : "Needs, Claims, Scenarios"} />
          <div className="grid gap-6 lg:grid-cols-3">
            {detail.needs.map((item) => (
              <InsightBlock items={item.tags} key={item.title} title={item.title} />
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <BrandRankingPanel
            contentUnit={isZh ? "内容" : "contents"}
            creatorUnit={isZh ? "达人" : "creators"}
            eyebrow={isZh ? "品牌" : "Brands"}
            items={detail.brands}
            locale={params.lang}
            primaryLabel={isZh ? "按互动" : "Engagement"}
            secondaryLabel={isZh ? "按达人" : "Creators"}
            title={isZh ? "品类品牌榜" : "Category Brand Ranking"}
          />
          <div className="grid gap-5 lg:grid-cols-2">
            {detail.topNotes.map((item) => (
              <NoteAnalysisCard
                commentLabel={isZh ? "评论" : "Comments"}
                href={withLocale(params.lang, `/datacenter/xhs/note/${item.noteId}`)}
                item={item}
                key={item.noteId}
                likeLabel={isZh ? "点赞" : "Likes"}
                saveLabel={isZh ? "收藏" : "Saves"}
              />
            ))}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          <InsightBlock items={detail.commentInsights.summary} title={isZh ? "AI 机会摘要" : "AI Opportunity Summary"} />
          <InsightBlock items={detail.commentInsights.comments} title={isZh ? "代表评论" : "Representative Comments"} />
          <InsightBlock items={detail.creators.map((item) => `${item.name} · ${item.direction} · ${item.followers}`)} title={isZh ? "达人机会" : "Creator Opportunity"} />
        </section>
      </main>
    </PageShell>
  );
}
