import type { Metadata } from "next";
import { cookies } from "next/headers";

import { DashboardHero } from "@/components/datacenter/dashboard-hero";
import { DistributionBars } from "@/components/datacenter/distribution-bars";
import { FilterChipBar } from "@/components/datacenter/filter-chip-bar";
import { InsightBlock } from "@/components/datacenter/insight-block";
import { MetricCard } from "@/components/datacenter/metric-card";
import { MiniAreaChart } from "@/components/datacenter/mini-area-chart";
import { NoteAnalysisCard } from "@/components/datacenter/note-analysis-card";
import { PageToolbar } from "@/components/datacenter/page-toolbar";
import { SectionHeading } from "@/components/datacenter/section-heading";
import { StackedAudienceBars } from "@/components/datacenter/stacked-audience-bars";
import { StatusOverviewStrip } from "@/components/datacenter/status-overview-strip";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { SESSION_COOKIE } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";
import { PageShell } from "@/layouts/page-shell";
import { getBrandDetail } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../../../../layout";

export async function generateMetadata({
  params
}: AppPageProps & { params: { lang: "zh" | "en"; slug: string } }): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(`${dictionary.xhs.brandCompetition} · ${params.slug}`, "Brand competition, audience profile, and AI-ready content analysis.");
}

export default async function BrandDetailPage({ params }: AppPageProps & { params: { lang: "zh" | "en"; slug: string } }) {
  const isZh = params.lang === "zh";
  const [dictionary, detail] = await Promise.all([getDictionary(params.lang), getBrandDetail(params.lang, params.slug)]);
  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={params.lang}
        pathname={withLocale(params.lang, `/datacenter/xhs/brand/${params.slug}`)}
      />

      <main className="mx-auto max-w-8xl space-y-8 px-4 pb-16 pt-8 md:px-8 md:space-y-10 md:pb-24">
        <PageToolbar backHref={withLocale(params.lang, "/datacenter/xhs")} backLabel={isZh ? "返回小红书" : "Back"} />

        <DashboardHero
          breadcrumb={detail.breadcrumb.join(" / ")}
          description={isZh ? "竞品、人群、反馈。" : "Competition, audience, feedback."}
          rightSlot={
            <div className="grid gap-4 sm:grid-cols-2">
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
          <MiniAreaChart items={detail.trend} eyebrow={isZh ? "趋势" : "Trend"} title={isZh ? "品牌走势" : "Brand Trend"} periodLabel={isZh ? "7天" : "7D"} />
          <div className="grid gap-6">
            <DistributionBars items={detail.competitors} title={isZh ? "竞品对比" : "Competitor Comparison"} />
            <DistributionBars items={detail.categoryMix} title={isZh ? "品类分布" : "Category Mix"} />
          </div>
        </section>

        <section>
          <SectionHeading
            eyebrow={isZh ? "人群画像" : "Audience Profile"}
            title={dictionary.common.audienceProfile}
            description={isZh ? "首版只展示年龄和性别。" : "v1 includes age and gender only."}
          />
          <div className="grid gap-6 lg:grid-cols-2">
            <StackedAudienceBars items={detail.audience.ageDistribution} title={isZh ? "年龄分布" : "Age Distribution"} />
            <StackedAudienceBars items={detail.audience.genderDistribution} title={isZh ? "性别分布" : "Gender Distribution"} />
          </div>
        </section>

        <section>
          <SectionHeading eyebrow={isZh ? "爆文" : "Top Content"} title={isZh ? "品牌高价值内容" : "Brand High-Value Content"} />
          <div className="grid gap-5 lg:grid-cols-3">
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
          <InsightBlock items={detail.feedback.positive} title={isZh ? "正向反馈" : "Positive Signals"} />
          <InsightBlock items={detail.feedback.caution} title={isZh ? "风险反馈" : "Caution Signals"} />
          <InsightBlock items={detail.feedback.rawComments} title={isZh ? "原始评论" : "Raw Comments"} />
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          {detail.aiDecisions.map((item) => (
            <InsightBlock items={item.points} key={item.title} title={item.title} />
          ))}
        </section>
      </main>
    </PageShell>
  );
}
