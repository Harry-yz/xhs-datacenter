import type { Metadata } from "next";

import { PlatformCard } from "@/components/datacenter/platform-card";
import { SiteHeader } from "@/components/navigation/site-header";
import { getDictionary } from "@/config/dictionaries";
import { buildMetadata } from "@/config/metadata";
import { PageShell } from "@/layouts/page-shell";
import { getPlatformCards } from "@/services/datacenter";
import { withLocale } from "@/utils/routes";

import type { AppPageProps } from "../layout";

export async function generateMetadata({ params }: AppPageProps): Promise<Metadata> {
  const dictionary = await getDictionary(params.lang);

  return buildMetadata(dictionary.navigation.home, dictionary.home.subtitle);
}

export default async function DataCenterHome({ params }: AppPageProps) {
  const isZh = params.lang === "zh";
  const pageTitle = isZh ? "Oran数据中心" : "Oran Data Center";
  const [dictionary, cards] = await Promise.all([getDictionary(params.lang), getPlatformCards(params.lang)]);

  return (
    <PageShell dark>
      <SiteHeader dictionary={dictionary} locale={params.lang} pathname={withLocale(params.lang, "/datacenter")} />

      <main className="mx-auto max-w-8xl px-4 pb-16 pt-6 md:px-8 md:pb-24 md:pt-8">
        <section className="mb-6 flex flex-col gap-3 md:mb-8 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <span className="text-[11px] uppercase tracking-[0.3em] text-foreground/38">Data Center</span>
            <h1 className="mt-2 max-w-4xl font-display text-[clamp(2.15rem,3.8vw,3.55rem)] leading-[0.96] text-foreground">
              {pageTitle}
            </h1>
          </div>
        </section>

        <section>
          <div className="mb-4">
            <div className="text-xs font-light uppercase tracking-[0.28em] text-foreground/45">
              {isZh ? "平台矩阵" : "Platform Matrix"}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {cards.map((item) => (
              <PlatformCard
                key={item.platform}
                href={item.href ? withLocale(params.lang, item.href) : undefined}
                item={item}
                creatorsLabel={dictionary.common.creators}
                notesLabel={dictionary.common.notes}
              />
            ))}
          </div>
        </section>
      </main>
    </PageShell>
  );
}
