import type { Metadata } from "next";
import { cookies } from "next/headers";

import { InsightBlock } from "@/components/datacenter/insight-block";
import { MetricCard } from "@/components/datacenter/metric-card";
import { PageToolbar } from "@/components/datacenter/page-toolbar";
import { SectionHeading } from "@/components/datacenter/section-heading";
import { StatusOverviewStrip } from "@/components/datacenter/status-overview-strip";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { SESSION_COOKIE } from "@/config/i18n";
import { isAuthenticatedSession } from "@/config/auth";
import { PageShell } from "@/layouts/page-shell";
import { getNoteDetail } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../../../../layout";

export async function generateMetadata({
  params
}: AppPageProps & { params: { lang: "zh" | "en"; noteId: string } }): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(`${dictionary.xhs.noteAnalysis} · ${params.noteId}`, "Structured note analysis with metrics, audience signals, comments, and AI marketing takeaways.");
}

export default async function NoteDetailPage({ params }: AppPageProps & { params: { lang: "zh" | "en"; noteId: string } }) {
  const isZh = params.lang === "zh";
  const [dictionary, detail] = await Promise.all([getDictionary(params.lang), getNoteDetail(params.lang, params.noteId)]);
  const authenticated = isAuthenticatedSession(cookies().get(SESSION_COOKIE)?.value);

  return (
    <PageShell dark>
      <SiteHeader
        authenticated={authenticated}
        dictionary={dictionary}
        locale={params.lang}
        pathname={withLocale(params.lang, `/datacenter/xhs/note/${params.noteId}`)}
      />

      <main className="mx-auto max-w-8xl space-y-8 px-4 pb-16 pt-8 md:px-8 md:space-y-10 md:pb-24">
        <PageToolbar backHref={withLocale(params.lang, "/datacenter/xhs")} backLabel={isZh ? "返回小红书" : "Back"} />

        <section className="grid gap-6 xl:grid-cols-[0.72fr_1.28fr]">
          <div className="section-frame">
            <div className="h-[420px] rounded-[1.8rem] bg-gradient-to-br from-[#f7c7b8] via-[#f1b8d6] to-[#a7d8ff]" />
          </div>
          <div className="section-frame">
            <div className="text-xs uppercase tracking-[0.26em] text-foreground/42">
              {detail.category} / {detail.brand}
            </div>
            <h1 className="mt-4 text-foreground">{detail.title}</h1>
            <div className="mt-3 text-sm text-foreground/55">
              {detail.author} · {detail.publishTime}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {detail.tags.map((tag) => (
                <span key={tag} className="rounded-full border border-border/30 bg-foreground/5 px-3 py-1 text-xs text-foreground/58">
                  {tag}
                </span>
              ))}
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {detail.metrics.map((item) => (
                <MetricCard item={item} key={item.label} />
              ))}
            </div>
          </div>
        </section>

        <StatusOverviewStrip items={detail.statusStats} />

        <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="section-frame">
            <SectionHeading eyebrow={isZh ? "内容视图" : "Content View"} title={isZh ? "结构化内容读取" : "Structured Read"} />
            <p>{detail.content}</p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
            {detail.aiBreakdown.map((item) => (
              <InsightBlock items={item.tags} key={item.title} title={item.title} />
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <InsightBlock items={detail.commentInsight.aiSummary} title={isZh ? "AI 评论摘要" : "AI Comment Summary"} />
          <InsightBlock items={detail.commentInsight.rawComments} title={isZh ? "代表评论" : "Representative Comments"} />
        </section>

        <section>
          <SectionHeading eyebrow={isZh ? "策略" : "Strategy"} title={isZh ? "可复用营销启发" : "Reusable Takeaways"} />
          <div className="grid gap-6 lg:grid-cols-3">
            {detail.strategyTakeaways.map((item) => (
              <InsightBlock items={[item]} key={item} title={isZh ? "启发" : "Takeaway"} />
            ))}
          </div>
        </section>
      </main>
    </PageShell>
  );
}
