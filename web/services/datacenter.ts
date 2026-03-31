import {
  audienceProfiles,
  brandDetail,
  brandRanking,
  categoryDetail,
  creatorOpportunities,
  hotCategories,
  noteCards,
  noteDetail,
  platformCards,
  searchWorkbench,
  xhsIndustries,
  xhsOverviewKpis,
  xhsTrend
} from "@/services/mock/datacenter";

import { env } from "@/config/env";
import { type Locale } from "@/config/i18n";
import {
  type CreatorOpportunityVM,
  type NoteAnalysisCardVM,
  type SearchWorkbenchVM,
  type TrendExplorerVM,
  type TrendSeriesPoint,
  type XhsLiveTotals,
  type XhsLiveMetrics
} from "@/types/datacenter";

async function wait(ms = 20) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

const platformNames = {
  zh: {
    Xiaohongshu: "小红书",
    Douyin: "抖音",
    TikTok: "Tiktok",
    Instagram: "Instagram",
    Facebook: "Facebook",
    Twitter: "Twitter"
  },
  en: {
    Xiaohongshu: "XiaoHongShu",
    Douyin: "Douyin",
    TikTok: "Tiktok",
    Instagram: "Instagram",
    Facebook: "Facebook",
    Twitter: "Twitter"
  }
} as const;

const platformDescriptions = {
  zh: {
    Xiaohongshu: "美妆 / 生活方式 / 达人信号",
    Douyin: "短视频 / 趋势 / 放大效应",
    TikTok: "全球 / 消费 / 创作者信号",
    Instagram: "视觉 / 品牌感 / 氛围内容",
    Facebook: "社群 / 需求 / 讨论深度",
    Twitter: "实时 / 观点 / 趋势动量"
  },
  en: {
    Xiaohongshu: "Beauty / Lifestyle / Creator Signals",
    Douyin: "Short Video / Trend / Amplification",
    TikTok: "Global / Consumer / Creator Signals",
    Instagram: "Visual / Brand Mood / Premium Content",
    Facebook: "Community / Demand / Discussion Depth",
    Twitter: "Realtime / Opinion / Trend Signals"
  }
} as const;

const zhToEn: Record<string, string> = {
  小红书: "XiaoHongShu",
  美妆: "Beauty",
  防晒: "Sunscreen",
  底妆: "Base Makeup",
  精华: "Serum",
  定妆: "Setting",
  卸妆清洁: "Cleansing",
  唇部彩妆: "Lip Makeup",
  图文: "Image Post",
  视频: "Video",
  内容量: "Contents",
  达人覆盖: "Creators",
  互动总量: "Engagement",
  高价值内容: "High-Value Posts",
  点赞: "Likes",
  收藏: "Saves",
  评论: "Comments",
  阅读: "Views",
  男性: "Male",
  女性: "Female",
  "18岁以下": "Under 18",
  "18-24岁": "18-24",
  "25-34岁": "25-34",
  "35-44岁": "35-44",
  "44岁以上": "45+",
  "Pain Points": "Pain Points",
  "Selling Points": "Selling Points",
  Scenarios: "Scenarios",
  Sentiment: "Sentiment"
};

function choose(locale: Locale, zh: string, en: string) {
  return locale === "zh" ? zh : en;
}

function translateLabel(locale: Locale, value: string) {
  return locale === "zh" ? value : zhToEn[value] ?? value;
}

function localizeNoteValue(locale: Locale, value: string) {
  return locale === "zh" ? value.replace(" Notes", " 笔记") : value;
}

function localizePeriods(locale: Locale, value: string) {
  if (locale === "en") {
    return value;
  }

  return (
    {
      "Last 7 Days": "近 7 天",
      "Last 30 Days": "近 30 天",
      "By Engagement": "按互动",
      "100+ Likes": "100+ 点赞"
    }[value] ?? value
  );
}

type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

type OverviewApiPoint = {
  stat_date?: string;
  date?: string;
  new_count?: number;
  total_count?: number;
};

type OverviewApiData = {
  summary?: {
    notes_total?: number;
    notes_like_ge_100?: number;
    creators_total?: number;
    comments_total?: number;
  };
  trend?: Record<string, OverviewApiPoint[]>;
  industries?: Array<{
    industry_key: string;
    industry_name: string;
    sort_no: number;
    note_count: number;
  }>;
  top_creators?: Array<{
    name: string;
    followers: number;
    note_count: number;
    interaction_total: number;
  }>;
};

type LiveApiData = {
  new_notes_24h?: number;
  updated_notes_30m?: number;
  new_comments_30m?: number;
  jobs_running?: number;
  generated_at?: string;
};

type LiveTotalsApiData = {
  notes_total?: number;
  creators_total?: number;
  comments_total?: number;
  generated_at?: string;
};

type SearchPending = {
  status: "pending";
  type: "category" | "creator";
  jobId?: string;
};

const PLATFORM_SPLIT_ORDER = ["Xiaohongshu", "Douyin", "TikTok", "Instagram", "Facebook", "Twitter"] as const;
const PLATFORM_SPLIT_RATIO: Record<(typeof PLATFORM_SPLIT_ORDER)[number], number> = {
  Xiaohongshu: 0.55,
  Douyin: 0.16,
  TikTok: 0.11,
  Instagram: 0.08,
  Facebook: 0.05,
  Twitter: 0.05
};

const INDUSTRY_META: Record<
  string,
  {
    zh: string;
    en: string;
    zhDesc: string;
    enDesc: string;
  }
> = {
  beauty: {
    zh: "美妆个护",
    en: "Beauty & Personal Care",
    zhDesc: "内容、达人与品牌信号",
    enDesc: "Content, creators, and brand signals"
  },
  fashion: {
    zh: "服饰穿搭",
    en: "Fashion",
    zhDesc: "穿搭参考与品牌提及",
    enDesc: "Outfit references and brand mentions"
  },
  mother_baby: {
    zh: "母婴亲子",
    en: "Mother & Baby",
    zhDesc: "产品信任与推荐循环",
    enDesc: "Product trust and recommendation loops"
  },
  food_drink: {
    zh: "食品饮料",
    en: "Food & Beverage",
    zhDesc: "口味、做法与场景内容",
    enDesc: "Taste, recipe, and scene-driven posts"
  },
  home_living: {
    zh: "家居家装",
    en: "Home Living",
    zhDesc: "家装灵感与实用内容",
    enDesc: "Decor inspiration and utility content"
  },
  consumer_electronics: {
    zh: "3C数码",
    en: "Consumer Electronics",
    zhDesc: "设备评测与生活效率",
    enDesc: "Device evaluation and lifestyle utility"
  },
  auto_travel: {
    zh: "汽车出行",
    en: "Auto Mobility",
    zhDesc: "生活方式与升级需求",
    enDesc: "Lifestyle ownership and upgrade behavior"
  },
  sports_outdoor: {
    zh: "运动户外",
    en: "Sports & Outdoor",
    zhDesc: "日常训练与体态管理",
    enDesc: "Routine and outdoor performance content"
  },
  pet: {
    zh: "宠物",
    en: "Pets",
    zhDesc: "养护、用品与情绪连接",
    enDesc: "Care, products, and emotional connection"
  },
  healthcare: {
    zh: "医疗健康",
    en: "Healthcare",
    zhDesc: "成分、功效与健康管理",
    enDesc: "Health efficacy and wellness discussions"
  },
  education: {
    zh: "教育培训",
    en: "Education",
    zhDesc: "学习效率与成长动机",
    enDesc: "Learning efficiency and growth intent"
  },
  travel_hotel: {
    zh: "文旅酒店",
    en: "Travel & Hotel",
    zhDesc: "目的地计划与攻略需求",
    enDesc: "Destination planning and travel demand"
  }
};

type FetchApiInit = RequestInit & {
  next?: {
    revalidate?: number;
    tags?: string[];
  };
};

async function fetchApi<T>(path: string, init?: FetchApiInit): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,
    cache: init?.cache ?? "no-store",
    next: init?.next,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    throw new Error(`API ${path} failed with status ${response.status}`);
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  return payload.data;
}

function toLocaleCount(locale: Locale, value: number) {
  return Math.max(0, Math.round(value)).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function toMonthDayLabel(dateText: string) {
  const date = new Date(`${dateText}T00:00:00Z`);
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${month}/${day}`;
}

function toCompactFollowers(locale: Locale, value: number) {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(2).replace(/\.00$/, "")}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  }
  return toLocaleCount(locale, value);
}

function mapLiveMetrics(payload: LiveApiData): XhsLiveMetrics {
  return {
    newNotes24h: Number(payload.new_notes_24h ?? 0),
    updatedNotes30m: Number(payload.updated_notes_30m ?? 0),
    newComments30m: Number(payload.new_comments_30m ?? 0),
    jobsRunning: Number(payload.jobs_running ?? 0),
    generatedAt: String(payload.generated_at ?? "")
  };
}

function mapLiveTotals(payload: LiveTotalsApiData): XhsLiveTotals {
  return {
    notesTotal: Number(payload.notes_total ?? 0),
    creatorsTotal: Number(payload.creators_total ?? 0),
    commentsTotal: Number(payload.comments_total ?? 0),
    generatedAt: String(payload.generated_at ?? "")
  };
}

function allocateByRatio(total: number) {
  const base = PLATFORM_SPLIT_ORDER.map((key) => ({
    key,
    value: Math.floor(total * PLATFORM_SPLIT_RATIO[key]),
    ratio: PLATFORM_SPLIT_RATIO[key]
  }));
  const used = base.reduce((sum, item) => sum + item.value, 0);
  let remainder = Math.max(0, total - used);

  const sortedByRatio = [...base].sort((a, b) => b.ratio - a.ratio);
  let index = 0;
  while (remainder > 0) {
    sortedByRatio[index % sortedByRatio.length].value += 1;
    remainder -= 1;
    index += 1;
  }

  const output = Object.fromEntries(
    sortedByRatio.map((item) => [item.key, item.value])
  ) as Record<(typeof PLATFORM_SPLIT_ORDER)[number], number>;

  return output;
}

function mapNoteRows(locale: Locale, rows: Array<Record<string, unknown>>): NoteAnalysisCardVM[] {
  const coverPalette = [
    "from-[#f7c7b8] via-[#f1b8d6] to-[#a7d8ff]",
    "from-[#f5d29d] via-[#f1c1cf] to-[#bfdef5]",
    "from-[#a7dbdb] via-[#b9dcff] to-[#e6caff]"
  ];

  return rows.map((item, index) => {
    const noteId = String(item.note_id ?? item.noteId ?? `note-${index + 1}`);
    const title = String(item.title ?? (locale === "zh" ? "未命名笔记" : "Untitled Note"));
    const author = String(item.author_nickname ?? item.author ?? (locale === "zh" ? "匿名作者" : "Unknown Author"));

    const likeCount = Number(item.like_count ?? item.likeCount ?? 0);
    const collectionCount = Number(item.collection_count ?? item.collectionCount ?? 0);
    const commentCount = Number(item.comment_count ?? item.commentCount ?? 0);
    const followers = Number(item.followers ?? item.author_fans_count ?? item.authorFansCount ?? 0);
    const tags = Array.isArray(item.tags) ? item.tags.map(String) : [];

    return {
      noteId,
      coverColor: coverPalette[index % coverPalette.length],
      title,
      author,
      followers: toCompactFollowers(locale, followers),
      likeCount: toLocaleCount(locale, likeCount),
      collectionCount: toLocaleCount(locale, collectionCount),
      commentCount: toLocaleCount(locale, commentCount),
      tags: tags.slice(0, 3),
      aiLabels: []
    };
  });
}

function mapCreatorRows(locale: Locale, rows: Array<Record<string, unknown>>): CreatorOpportunityVM[] {
  return rows.map((item) => {
    const name = String(item.author_nickname ?? item.name ?? item.author_id ?? "");
    const followers = Number(item.followers ?? item.fans_count ?? 0);
    const notesCount = Number(item.note_count ?? item.notes ?? 0);
    const totalInteractions = Number(item.interaction_total ?? item.sumStat ?? 0);
    const tags = Array.isArray(item.tags) ? item.tags.map(String).filter(Boolean) : [];
    const direction = tags.length ? tags.slice(0, 2).join(" / ") : choose(locale, "内容达人", "Content Creator");

    return {
      name: name || choose(locale, "未知达人", "Unknown Creator"),
      followers: toCompactFollowers(locale, followers),
      direction,
      cpe: "-",
      notesCount,
      totalInteractions
    };
  });
}

function mapOverviewTrendWindow(points: OverviewApiPoint[]) {
  return points.map((item) => ({
    date: String(item.stat_date ?? item.date ?? ""),
    value: Number(item.new_count ?? 0)
  }));
}

function toIsoDate(value: Date) {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, "0");
  const day = String(value.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildWindowSeries({
  days,
  start,
  end,
  amplitude,
  endDate
}: {
  days: number;
  start: number;
  end: number;
  amplitude: number;
  endDate: Date;
}) {
  const points: TrendSeriesPoint[] = [];

  for (let index = 0; index < days; index += 1) {
    const progress = index / Math.max(days - 1, 1);
    const trendValue = start + (end - start) * progress;
    const seasonal = Math.sin((index + 1) * 0.51) * amplitude + Math.cos((index + 1) * 0.23) * amplitude * 0.4;
    const value = Math.max(120, Math.round(trendValue + seasonal));

    const currentDate = new Date(endDate);
    currentDate.setUTCDate(endDate.getUTCDate() - (days - 1 - index));

    points.push({
      date: toIsoDate(currentDate),
      value
    });
  }

  return points;
}

function applyTail(
  source: TrendSeriesPoint[],
  tail: Array<{
    value: number;
  }>
) {
  const output = [...source];
  const offset = Math.max(output.length - tail.length, 0);

  tail.forEach((item, index) => {
    const target = output[offset + index];

    if (target) {
      output[offset + index] = {
        ...target,
        value: item.value
      };
    }
  });

  return output;
}

function buildTrendExplorer(locale: Locale): TrendExplorerVM {
  const anchorDate = new Date(Date.UTC(2026, 2, 25));

  const window7 = xhsTrend.map((item, index) => {
    const currentDate = new Date(anchorDate);
    currentDate.setUTCDate(anchorDate.getUTCDate() - (xhsTrend.length - 1 - index));
    return {
      date: toIsoDate(currentDate),
      value: item.value
    };
  });

  const window30 = applyTail(
    buildWindowSeries({
      days: 30,
      start: 520,
      end: 1910,
      amplitude: 110,
      endDate: anchorDate
    }),
    xhsTrend
  );

  const window90 = applyTail(
    buildWindowSeries({
      days: 90,
      start: 220,
      end: 1910,
      amplitude: 150,
      endDate: anchorDate
    }),
    xhsTrend
  );

  return {
    metricKey: "daily_new_notes",
    metricLabel: choose(locale, "日新增笔记数", "Daily New Notes"),
    defaultWindow: 30,
    windows: {
      7: window7,
      30: window30,
      90: window90
    }
  };
}

export async function getPlatformCards(locale: Locale) {
  try {
    const overview = await fetchApi<OverviewApiData>("/dashboard/xhs/overview?days=90", {
      cache: "force-cache",
      next: { revalidate: 30 }
    });
    const summary = overview.summary ?? {};
    const totalNotes = Number(summary.notes_total ?? 0);
    const totalCreators = Number(summary.creators_total ?? 0);
    const noteSplit = allocateByRatio(totalNotes);
    const creatorSplit = allocateByRatio(totalCreators);

    return platformCards.map((item) => {
      const key = item.platform as (typeof PLATFORM_SPLIT_ORDER)[number];
      const notes = toLocaleCount(locale, noteSplit[key] ?? 0);
      const creators = toLocaleCount(locale, creatorSplit[key] ?? 0);

      return {
        ...item,
        notes,
        creators,
        platform: platformNames[locale][item.platform as keyof (typeof platformNames)[Locale]] ?? item.platform,
        description: platformDescriptions[locale][item.platform as keyof (typeof platformDescriptions)[Locale]] ?? item.description
      };
    });
  } catch {
    await wait();

    return platformCards.map((item) => ({
      ...item,
      platform: platformNames[locale][item.platform as keyof (typeof platformNames)[Locale]] ?? item.platform,
      description: platformDescriptions[locale][item.platform as keyof (typeof platformDescriptions)[Locale]] ?? item.description
    }));
  }
}

export async function getXhsOverview(locale: Locale) {
  try {
    const overview = await fetchApi<OverviewApiData>("/dashboard/xhs/overview?days=90", {
      cache: "force-cache",
      next: { revalidate: 15 }
    });
    const summary = overview.summary ?? {};
    const trend = overview.trend ?? {};
    const trend7 = mapOverviewTrendWindow(trend["7"] ?? []);
    const trend30 = mapOverviewTrendWindow(trend["30"] ?? []);
    const trend90 = mapOverviewTrendWindow(trend["90"] ?? []);

    const trendExplorer: TrendExplorerVM =
      trend7.length > 0 && trend30.length > 0 && trend90.length > 0
        ? {
            metricKey: "daily_new_notes",
            metricLabel: choose(locale, "日新增笔记数", "Daily New Notes"),
            defaultWindow: 30,
            windows: {
              7: trend7,
              30: trend30,
              90: trend90
            }
          }
        : buildTrendExplorer(locale);

    const trends = (trend["7"] ?? []).map((item) => ({
      label: toMonthDayLabel(String(item.stat_date ?? item.date ?? "")),
      value: Number(item.new_count ?? 0)
    }));

    const industries =
      (overview.industries ?? []).map((item) => {
        const meta = INDUSTRY_META[item.industry_key] ?? {
          zh: item.industry_name,
          en: item.industry_name,
          zhDesc: "行业数据观测",
          enDesc: "Industry data tracking"
        };
        return {
          industryKey: item.industry_key,
          name: locale === "zh" ? meta.zh : meta.en,
          description: locale === "zh" ? meta.zhDesc : meta.enDesc,
          value: `${toLocaleCount(locale, Number(item.note_count ?? 0))} ${locale === "zh" ? "笔记" : "Notes"}`,
          sortNo: Number(item.sort_no ?? 0)
        };
      }) ?? [];

    const creators: CreatorOpportunityVM[] =
      (overview.top_creators ?? []).slice(0, 20).map((item) => ({
        name: String(item.name ?? ""),
        followers: toCompactFollowers(locale, Number(item.followers ?? 0)),
        direction: choose(locale, "高互动达人", "High Engagement Creator"),
        cpe: "-"
      })) ?? [];

    return {
      kpis: [
        { label: locale === "zh" ? "笔记" : "Notes", value: toLocaleCount(locale, Number(summary.notes_total ?? 0)) },
        { label: locale === "zh" ? "达人" : "Creators", value: toLocaleCount(locale, Number(summary.creators_total ?? 0)) },
        { label: locale === "zh" ? "评论" : "Comments", value: toLocaleCount(locale, Number(summary.comments_total ?? 0)) },
        { label: locale === "zh" ? "100+ 内容" : "100+ Posts", value: toLocaleCount(locale, Number(summary.notes_like_ge_100 ?? 0)), tone: "accent" as const }
      ],
      trends: trends.length ? trends : xhsTrend,
      trendExplorer,
      industries: (industries.length ? industries : xhsIndustries).sort((a, b) => ("sortNo" in a ? Number((a as { sortNo: number }).sortNo) : 0) - ("sortNo" in b ? Number((b as { sortNo: number }).sortNo) : 0)).map((item) => {
        const { sortNo: _sortNo, ...rest } = item as typeof item & { sortNo?: number };
        return rest;
      }),
      hotCategories: hotCategories.map((item) => ({
        ...item,
        name: translateLabel(locale, item.name),
        description:
          locale === "zh"
            ? item.description
            : {
                防晒: "Commute / outdoor / UV defense",
                底妆: "Coverage / texture / longwear",
                精华: "Repair / brightening / efficacy",
                定妆: "Oil control / blur / commute",
                卸妆清洁: "Gentle / cleansing / sensitive skin",
                唇部彩妆: "Shade / brightening / mood look"
              }[item.name] ?? item.description,
        notes: localizeNoteValue(locale, item.notes)
      })),
      brands: brandRanking,
      topNotes: noteCards,
      creators: creators.length ? creators : creatorOpportunities,
      aiCards: [
        locale === "zh"
          ? {
              title: "热点总结",
              points: ["美妆仍然是最高密度内容池", "防晒、底妆、精华是当前最有价值的观测带"]
            }
          : {
              title: "Heat Summary",
              points: ["Beauty remains the highest-density content pool.", "Sunscreen, base makeup, and serums are the most valuable lanes right now."]
            },
        locale === "zh"
          ? {
              title: "品牌机会",
              points: ["头部品牌心智稳定，但平替和质地比较仍有突破空间", "收藏高的内容更偏教程和场景化表达"]
            }
          : {
              title: "Brand Opportunity",
              points: ["Top brands stay strong, but dupes and texture comparisons still open room.", "Save-heavy posts lean toward tutorial and scenario framing."]
            }
      ]
    };
  } catch {
    await wait();

    return {
      kpis: xhsOverviewKpis.map((item) => ({
        ...item,
        label:
          locale === "zh"
            ? {
                Notes: "笔记",
                Creators: "达人",
                Comments: "评论",
                "100+ Posts": "100+ 内容"
              }[item.label] ?? item.label
            : item.label
      })),
      trends: xhsTrend,
      trendExplorer: buildTrendExplorer(locale),
      industries: xhsIndustries.map((item) => ({
        ...item,
        name:
          locale === "zh"
            ? {
                Beauty: "美妆",
                "Mother & Baby": "母婴",
                Fashion: "时尚",
                Food: "美食",
                Travel: "旅行",
                Home: "家居",
                Digital: "数码",
                Fitness: "运动",
                Pets: "宠物",
                Education: "教育",
                Automotive: "汽车",
                Luxury: "奢品"
              }[item.name] ?? item.name
            : item.name,
        description:
          locale === "zh"
            ? {
                Beauty: "内容、达人与品牌信号",
                "Mother & Baby": "产品信任与推荐循环",
                Fashion: "穿搭参考与品牌提及",
                Food: "口味、做法与场景内容",
                Travel: "目的地计划与攻略需求",
                Home: "家装灵感与实用内容",
                Digital: "设备评测与生活效率",
                Fitness: "日常训练与体态管理",
                Pets: "养护、用品与情绪连接",
                Education: "学习效率与成长动机",
                Automotive: "生活方式与升级需求",
                Luxury: "高端欲望与购买信心"
              }[item.name] ?? item.description
            : item.description,
        value: localizeNoteValue(locale, item.value)
      })),
      hotCategories: hotCategories.map((item) => ({
        ...item,
        name: translateLabel(locale, item.name),
        description:
          locale === "zh"
            ? item.description
            : {
                防晒: "Commute / outdoor / UV defense",
                底妆: "Coverage / texture / longwear",
                精华: "Repair / brightening / efficacy",
                定妆: "Oil control / blur / commute",
                卸妆清洁: "Gentle / cleansing / sensitive skin",
                唇部彩妆: "Shade / brightening / mood look"
              }[item.name] ?? item.description,
        notes: localizeNoteValue(locale, item.notes)
      })),
      brands: brandRanking,
      topNotes: noteCards,
      creators: creatorOpportunities,
      aiCards: [
        locale === "zh"
          ? {
              title: "热点总结",
              points: ["美妆仍然是最高密度内容池", "防晒、底妆、精华是当前最有价值的观测带"]
            }
          : {
              title: "Heat Summary",
              points: ["Beauty remains the highest-density content pool.", "Sunscreen, base makeup, and serums are the most valuable lanes right now."]
            },
        locale === "zh"
          ? {
              title: "品牌机会",
              points: ["头部品牌心智稳定，但平替和质地比较仍有突破空间", "收藏高的内容更偏教程和场景化表达"]
            }
          : {
              title: "Brand Opportunity",
              points: ["Top brands stay strong, but dupes and texture comparisons still open room.", "Save-heavy posts lean toward tutorial and scenario framing."]
            }
      ]
    };
  }
}

export async function getXhsLiveMetrics(): Promise<XhsLiveMetrics | null> {
  try {
    const payload = await fetchApi<LiveApiData>("/dashboard/xhs/live");
    return mapLiveMetrics(payload);
  } catch {
    return null;
  }
}

export async function getXhsLiveTotals(): Promise<XhsLiveTotals | null> {
  try {
    const payload = await fetchApi<LiveTotalsApiData>("/dashboard/xhs/live-totals", {
      cache: "force-cache",
      next: { revalidate: 60 }
    });
    return mapLiveTotals(payload);
  } catch {
    return null;
  }
}

export async function getSearchWorkbench(locale: Locale, query?: Record<string, string>): Promise<SearchWorkbenchVM> {
  const fallback: SearchWorkbenchVM = {
    ...searchWorkbench,
    creators: creatorOpportunities,
    summary: searchWorkbench.summary.map((item) => ({
      ...item,
      label:
        locale === "zh"
          ? {
              Results: "结果",
              Creators: "达人",
              Comments: "评论",
              Brands: "品牌"
            }[item.label] ?? item.label
          : item.label
    })),
    filters: searchWorkbench.filters.map((item) => ({
      ...item,
      label:
        locale === "zh"
          ? {
              Query: "搜索",
              "Min Likes": "最低点赞",
              "Min Saves": "最低收藏",
              Sort: "排序",
              Window: "时间窗"
            }[item.label] ?? item.label
          : item.label,
      value: localizePeriods(locale, item.value)
    })),
    statusStats: searchWorkbench.statusStats.map((item) => ({
      ...item,
      label:
        locale === "zh"
          ? {
              "Content Velocity": "内容增速",
              "Save Bias": "收藏偏好",
              "High Value Share": "高价值占比"
            }[item.label] ?? item.label
          : item.label,
      helper:
        locale === "zh"
          ? {
              "vs previous 7 days": "对比前 7 天",
              "save-to-comment ratio": "收藏与评论比",
              "1000+ like posts": "点赞 1000+ 占比"
            }[item.helper ?? ""] ?? item.helper
          : item.helper
    })),
    categoryDistribution: searchWorkbench.categoryDistribution.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    contentTypes: searchWorkbench.contentTypes.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    }))
  };

  const keyword = typeof query?.q === "string" && query.q.trim() ? query.q.trim() : locale === "zh" ? "防晒" : "sunscreen";
  const activeType = query?.type === "creator" ? "creator" : "category";
  const page = Math.max(1, Number.parseInt(String(query?.page ?? "1"), 10) || 1);
  const industry = typeof query?.industry === "string" && query.industry.trim() ? query.industry.trim() : undefined;
  const minLike = Math.max(1, Number.parseInt(String(query?.min_like ?? "1"), 10) || 1);
  const sortRaw =
    typeof query?.sort === "string" && query.sort.trim()
      ? query.sort.trim()
      : activeType === "creator"
        ? "followers"
        : "stat";
  const sort =
    activeType === "creator"
      ? (["followers", "notes", "sumStat"].includes(sortRaw) ? sortRaw : "followers")
      : (["stat", "like", "read", "comments"].includes(sortRaw) ? sortRaw : "stat");
  const order = query?.order === "asc" ? "asc" : "desc";

  try {
    const size = 30;

    const categoryRequest = () =>
      fetchApi<Record<string, unknown>>("/search/brand-category", {
        method: "POST",
        body: JSON.stringify({
          query: keyword,
          mode: "category",
          industry,
          sort: activeType === "category" ? sort : "stat",
          order: activeType === "category" ? order : "desc",
          page,
          size,
          date_range: 30,
          freshness_hours: 24,
          min_like: minLike,
          force_refresh: false
        })
      });
    const creatorRequest = () =>
      fetchApi<Record<string, unknown>>("/search/influencer", {
        method: "POST",
        body: JSON.stringify({
          query: keyword,
          industry,
          sort: activeType === "creator" ? sort : "followers",
          order: activeType === "creator" ? order : "desc",
          page,
          size,
          date_range: 30,
          freshness_hours: 24,
          force_refresh: false
        })
      });

    const [categoryRawResult, creatorRawResult] =
      activeType === "creator"
        ? await Promise.allSettled([
            Promise.resolve<Record<string, unknown>>({
              status: "ready",
              items: [],
              notes: [],
              pagination: { total: 0, page, size, has_more: false }
            }),
            creatorRequest()
          ])
        : await Promise.allSettled([
            categoryRequest(),
            Promise.resolve<Record<string, unknown>>({
              status: "ready",
              items: [],
              notes: [],
              pagination: { total: 0, page, size, has_more: false }
            })
          ]);

    const categoryRaw =
      categoryRawResult.status === "fulfilled"
        ? categoryRawResult.value
        : {
            status: "failed",
            items: [],
            notes: [],
            pagination: { total: 0, page, size, has_more: false }
          };
    const creatorRaw =
      creatorRawResult.status === "fulfilled"
        ? creatorRawResult.value
        : {
            status: "failed",
            items: [],
            notes: [],
            pagination: { total: 0, page, size, has_more: false }
          };

    let pending: SearchPending | undefined;

    const resolveReadyPayload = async (
      payload: Record<string, unknown>,
      type: "category" | "creator"
    ) => {
      const status = String(payload.status ?? "");
      if (status === "ready") {
        return payload;
      }

      if (status === "pending") {
        const jobId = String(payload.job_id ?? "");
        if (jobId) {
          pending = {
            status: "pending",
            type,
            jobId
          };
        }
      }

      return payload;
    };

    const categoryReady = await resolveReadyPayload(categoryRaw, "category");
    const creatorReady = await resolveReadyPayload(creatorRaw, "creator");

    const categoryItemsRaw = Array.isArray(categoryReady.items) ? (categoryReady.items as Array<Record<string, unknown>>) : [];
    const creatorItemsRaw = Array.isArray(creatorReady.items) ? (creatorReady.items as Array<Record<string, unknown>>) : [];
    const creatorNotesRaw = Array.isArray(creatorReady.notes) ? (creatorReady.notes as Array<Record<string, unknown>>) : [];
    const categoryTotal = Number((categoryReady.pagination as Record<string, unknown> | undefined)?.total ?? categoryItemsRaw.length);
    const creatorTotal = Number((creatorReady.pagination as Record<string, unknown> | undefined)?.total ?? creatorItemsRaw.length);

    const notes = mapNoteRows(locale, categoryItemsRaw.length ? categoryItemsRaw : creatorNotesRaw);
    const creators = mapCreatorRows(locale, creatorItemsRaw);

    const totalComments = notes.reduce((sum, item) => sum + Number(item.commentCount.replace(/,/g, "")), 0);
    const summaryResults = activeType === "creator" ? Math.max(0, creatorTotal) : Math.max(0, categoryTotal);

    return {
      ...fallback,
      notes,
      creators,
      pending,
      resultTotals: {
        category: Math.max(0, categoryTotal),
        creator: Math.max(0, creatorTotal),
        page,
        size
      },
      summary: [
        { label: locale === "zh" ? "结果" : "Results", value: toLocaleCount(locale, summaryResults) },
        { label: locale === "zh" ? "达人" : "Creators", value: toLocaleCount(locale, creatorTotal) },
        { label: locale === "zh" ? "评论" : "Comments", value: toLocaleCount(locale, totalComments) },
        { label: locale === "zh" ? "品牌" : "Brands", value: "-" }
      ],
      filters: [
        { label: locale === "zh" ? "搜索" : "Query", value: keyword, active: true },
        { label: locale === "zh" ? "排序" : "Sort", value: locale === "zh" ? "按互动" : "By Engagement" },
        { label: locale === "zh" ? "时间窗" : "Window", value: locale === "zh" ? "近 30 天" : "Last 30 Days" }
      ]
    };
  } catch {
    await wait();
    return fallback;
  }
}

export async function getCategoryDetail(locale: Locale, _slug: string) {
  if (!env.useMockData) {
    // Reserved for the real adapter; the view models stay stable so pages do not need to change.
  }

  await wait();

  return {
    ...categoryDetail,
    breadcrumb: categoryDetail.breadcrumb.map((item) => translateLabel(locale, item)),
    heroSummary: choose(locale, "通勤、户外和控油诉求正在拉动这个品类。", categoryDetail.heroSummary),
    filters: categoryDetail.filters.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label),
      value: localizePeriods(locale, translateLabel(locale, item.value))
    })),
    statusStats: categoryDetail.statusStats.map((item) => ({
      ...item,
      label: choose(
        locale,
        {
          "Scenario Heat": "场景热度",
          "Claim Shift": "诉求变化",
          "Demand Signal": "需求信号"
        }[item.label] ?? item.label,
        item.label
      ),
      helper: choose(
        locale,
        {
          "dominant save context": "主导收藏场景",
          "highest gain selling point": "增长最快卖点",
          "strongest comment theme": "最强评论主题"
        }[item.helper ?? ""] ?? item.helper ?? "",
        item.helper ?? ""
      )
    })),
    kpis: categoryDetail.kpis.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    opportunityCards: categoryDetail.opportunityCards.map((item) => ({
      ...item,
      title: choose(
        locale,
        {
          "热点场景": "热点场景",
          "上升诉求": "上升诉求",
          "建议切入": "建议切入"
        }[item.title] ?? item.title,
        {
          "热点场景": "Hot Scenario",
          "上升诉求": "Rising Claim",
          "建议切入": "Suggested Entry"
        }[item.title] ?? item.title
      ),
      description: choose(
        locale,
        {
          "Morning commute and travel continue to dominate saves and shares.": "通勤和出游内容仍然主导收藏与分享。",
          "Fast set and no white cast language is trending up in high-performing posts.": "成膜快和不假白正在高表现内容里持续升温。",
          "Build a creator angle around high-heat, long-wear routines.": "建议围绕高温、长时持妆场景去组织达人内容。"
        }[item.description] ?? item.description,
        item.description
      )
    })),
    needs: categoryDetail.needs.map((item) => ({
      ...item,
      title: translateLabel(locale, item.title)
    }))
  };
}

export async function getBrandDetail(locale: Locale, _slug: string) {
  if (!env.useMockData) {
    // Reserved for the real adapter; the view models stay stable so pages do not need to change.
  }

  await wait();

  return {
    ...brandDetail,
    breadcrumb: brandDetail.breadcrumb.map((item) => translateLabel(locale, item)),
    filters: brandDetail.filters.map((item) => ({
      ...item,
      label: choose(
        locale,
        {
          Brand: "品牌",
          Window: "时间窗",
          Sort: "排序"
        }[item.label] ?? item.label,
        item.label
      ),
      value: localizePeriods(locale, item.value)
    })),
    statusStats: brandDetail.statusStats.map((item) => ({
      ...item,
      label: choose(
        locale,
        {
          "Share of Voice": "声量占比",
          "Creator Spread": "达人覆盖",
          "Save Intention": "收藏倾向"
        }[item.label] ?? item.label,
        item.label
      ),
      helper: choose(
        locale,
        {
          "within tracked beauty brands": "在已追踪美妆品牌内",
          "distinct creator coverage": "去重达人覆盖数",
          "content skews toward save-heavy formats": "内容更偏高收藏表达"
        }[item.helper ?? ""] ?? item.helper ?? "",
        item.helper ?? ""
      )
    })),
    kpis: brandDetail.kpis.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    categoryMix: brandDetail.categoryMix.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    audience: await getAudienceProfile(locale),
    aiDecisions: brandDetail.aiDecisions.map((item) => ({
      ...item,
      title: translateLabel(locale, item.title),
      points:
        locale === "zh"
          ? item.points
          : item.points.map((point) =>
              ({
                "色号和高级感表达强": "Shade storytelling and premium mood are strong.",
                "品牌心智高，适合做形象向内容": "Strong brand recall fits image-led content.",
                "价格敏感明显": "Price sensitivity is obvious.",
                "肤质适配信息仍需补强": "Skin-type fit still needs stronger proof.",
                "强化不同肤质场景评测": "Build clearer tests across skin types.",
                "用更明确的妆效对比拉升收藏与转发": "Use sharper result comparisons to lift saves and shares."
              }[point] ?? point)
            )
    }))
  };
}

export async function getNoteDetail(locale: Locale, _noteId: string) {
  if (!env.useMockData) {
    // Reserved for the real adapter; the view models stay stable so pages do not need to change.
  }

  await wait();

  return {
    ...noteDetail,
    category: translateLabel(locale, noteDetail.category),
    statusStats: noteDetail.statusStats.map((item) => ({
      ...item,
      label: choose(
        locale,
        {
          "Hook Pattern": "开头模式",
          "Audience Signal": "人群信号",
          "Content Type": "内容类型"
        }[item.label] ?? item.label,
        item.label
      ),
      helper: choose(
        locale,
        {
          "drives strongest save intent": "最能拉动收藏意图",
          "tutorial-style comments dominate": "教程型评论明显更多",
          "better than pure product pitch": "强于纯产品介绍"
        }[item.helper ?? ""] ?? item.helper ?? "",
        item.helper ?? ""
      )
    })),
    metrics: noteDetail.metrics.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    aiBreakdown: noteDetail.aiBreakdown.map((item) => ({
      ...item,
      title: translateLabel(locale, item.title)
    })),
    strategyTakeaways:
      locale === "zh"
        ? noteDetail.strategyTakeaways
        : [
            "Strong before-after contrast is the first hook.",
            "Tutorial structure increases save intent.",
            "Best reused in highly replicable base-makeup content."
          ]
  };
}

export async function getAudienceProfile(locale: Locale) {
  if (!env.useMockData) {
    // Reserved for the real adapter; the view models stay stable so pages do not need to change.
  }

  await wait();

  return {
    ageDistribution: audienceProfiles.ageDistribution.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    })),
    genderDistribution: audienceProfiles.genderDistribution.map((item) => ({
      ...item,
      label: translateLabel(locale, item.label)
    }))
  };
}
