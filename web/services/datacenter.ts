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
import { buildSearchResultsSlice, createDefaultSearchPayload } from "@/lib/search-workbench";
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

type LiveIndustriesApiData = {
  items?: Array<{
    industry_key?: string;
    industry_name?: string;
    note_count?: number;
  }>;
  generated_at?: string;
};

type SearchPending = {
  status: "pending" | "failed";
  type: "category" | "creator";
  jobId?: string;
  pendingReason?: string;
  nextPollAfterMs?: number;
  dataFreshnessSeconds?: number;
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
  timeoutMs?: number;
};

class ApiRequestError extends Error {
  readonly status: number;
  readonly errorType: "upstream_timeout" | "upstream_redirect" | "upstream_status";
  readonly path: string;

  constructor(params: {
    path: string;
    status: number;
    errorType: "upstream_timeout" | "upstream_redirect" | "upstream_status";
    message: string;
  }) {
    super(params.message);
    this.name = "ApiRequestError";
    this.path = params.path;
    this.status = params.status;
    this.errorType = params.errorType;
  }
}

async function fetchApi<T>(path: string, init?: FetchApiInit): Promise<T> {
  const hasRevalidate = typeof init?.next?.revalidate === "number";
  const timeoutMs = Math.max(1000, Number(init?.timeoutMs ?? 4500));
  const apiUrl = `${env.internalApiBaseUrl}${path}`;
  try {
    const response = await fetch(apiUrl, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(timeoutMs),
      cache: hasRevalidate ? undefined : (init?.cache ?? "no-store"),
      next: init?.next,
      redirect: "manual",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });

    const redirectedMisconfigured =
      response.redirected ||
      response.type === "opaqueredirect" ||
      Boolean(response.headers.get("location")) ||
      (response.status >= 300 && response.status < 400);
    if (redirectedMisconfigured) {
      throw new ApiRequestError({
        path,
        status: response.status,
        errorType: "upstream_redirect",
        message: `API ${path} redirected unexpectedly`
      });
    }

    if (!response.ok) {
      throw new ApiRequestError({
        path,
        status: response.status,
        errorType: "upstream_status",
        message: `API ${path} failed with status ${response.status}`
      });
    }

    const payload = (await response.json()) as ApiEnvelope<T>;
    return payload.data;
  } catch (error) {
    const name = error && typeof error === "object" && "name" in error ? String((error as { name?: unknown }).name ?? "") : "";
    const message = error instanceof Error ? error.message : String(error ?? "");
    const timeout = name === "AbortError" || name === "TimeoutError" || /timeout|timed out|abort/i.test(message);
    if (timeout) {
      throw new ApiRequestError({
        path,
        status: 504,
        errorType: "upstream_timeout",
        message: `API ${path} timeout`
      });
    }
    throw error;
  }
}

async function withRetry<T>(
  request: () => Promise<T>,
  options?: {
    attempts?: number;
    retryDelayMs?: number;
  }
): Promise<{ ok: true; value: T } | { ok: false; error: unknown }> {
  const attempts = Math.max(1, options?.attempts ?? 2);
  const retryDelayMs = Math.max(0, options?.retryDelayMs ?? 250);
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const value = await request();
      return { ok: true, value };
    } catch (error) {
      if (attempt >= attempts) {
        return { ok: false, error };
      }
      await wait(retryDelayMs * attempt);
    }
  }
  return { ok: false, error: new Error("request failed") };
}

function getErrorName(error: unknown) {
  if (error && typeof error === "object" && "name" in error) {
    return String((error as { name?: unknown }).name ?? "");
  }
  return "";
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error ?? "");
}

function isTimeoutOrAbortError(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.errorType === "upstream_timeout";
  }
  const name = getErrorName(error);
  if (name === "AbortError" || name === "TimeoutError") {
    return true;
  }
  const message = getErrorMessage(error).toLowerCase();
  return (
    message.includes("timeout") ||
    message.includes("timed out") ||
    message.includes("abort")
  );
}

function isUpstreamMisconfiguredError(error: unknown) {
  if (!(error instanceof ApiRequestError)) {
    return false;
  }
  return error.errorType === "upstream_redirect" || error.status === 405;
}

function toLocaleCount(locale: Locale, value: number) {
  return Math.max(0, Math.round(value)).toLocaleString(locale === "zh" ? "zh-CN" : "en-US");
}

function parseMetricValue(raw: string | undefined) {
  if (!raw) {
    return 0;
  }
  const parsed = Number(raw.replace(/[^\d.-]/g, ""));
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
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
  return rows.map((item, index) => {
    const authorId = String(item.author_id ?? item.authorId ?? "").trim();
    const name = String(item.author_nickname ?? item.name ?? authorId ?? "");
    const followers = Number(item.followers ?? item.fans_count ?? 0);
    const notesCount = Number(item.note_count ?? item.notes ?? 0);
    const totalInteractions = Number(item.interaction_total ?? item.sumStat ?? 0);
    const tags = Array.isArray(item.tags) ? item.tags.map(String).filter(Boolean) : [];
    const direction = tags.length ? tags.slice(0, 2).join(" / ") : choose(locale, "内容达人", "Content Creator");
    const rawProfileUrl = String(item.creator_home_url ?? item.anchor_link ?? item.profile_url ?? "").trim();
    const profileUrl =
      rawProfileUrl ||
      (authorId ? `https://www.xiaohongshu.com/user/profile/${authorId}` : "");

    return {
      authorId: authorId || `creator-${index + 1}`,
      name: name || choose(locale, "未知达人", "Unknown Creator"),
      followers: toCompactFollowers(locale, followers),
      direction,
      cpe: "-",
      notesCount,
      totalInteractions,
      profileUrl
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
    const [liveTotalsResp, overviewResp] = await Promise.all([
      withRetry(
        () =>
          fetchApi<LiveTotalsApiData>("/dashboard/xhs/live-totals", {
            next: { revalidate: 30 },
            timeoutMs: 1200
          }),
        { attempts: 1 }
      ),
      withRetry(
        () =>
          fetchApi<OverviewApiData>("/dashboard/xhs/overview?days=90", {
            next: { revalidate: 30 },
            timeoutMs: 1200
          }),
        { attempts: 1 }
      )
    ]);
    const liveTotals = liveTotalsResp.ok ? liveTotalsResp.value : null;
    const overview = overviewResp.ok ? overviewResp.value : null;
    const summary = overview?.summary ?? {};
    const totalNotes = Number(liveTotals?.notes_total ?? summary.notes_total ?? 0);
    const totalCreators = Number(liveTotals?.creators_total ?? summary.creators_total ?? 0);
    const noteSplit = allocateByRatio(totalNotes);
    const creatorSplit = allocateByRatio(totalCreators);

    return platformCards.map((item) => {
      const key = item.platform as (typeof PLATFORM_SPLIT_ORDER)[number];
      const notes =
        key === "Xiaohongshu"
          ? toLocaleCount(locale, totalNotes)
          : toLocaleCount(locale, noteSplit[key] ?? 0);
      const creators =
        key === "Xiaohongshu"
          ? toLocaleCount(locale, totalCreators)
          : toLocaleCount(locale, creatorSplit[key] ?? 0);

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
  const fallbackTrendExplorer = buildTrendExplorer(locale);
  const fallbackIndustries = xhsIndustries.map((item) => ({
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
  }));
  const fallbackAiCards = [
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
  ];

  try {
    // 首屏优先轻接口：先拿 totals + industries，重 overview 超时快速降级。
    const [totalsResp, industriesResp, overviewResp] = await Promise.all([
      withRetry(
        () =>
          fetchApi<LiveTotalsApiData>("/dashboard/xhs/live-totals", {
            next: { revalidate: 30 },
            timeoutMs: 1200
          }),
        { attempts: 1 }
      ),
      withRetry(
        () =>
          fetchApi<LiveIndustriesApiData>("/dashboard/xhs/live-industries", {
            next: { revalidate: 60 },
            timeoutMs: 1200
          }),
        { attempts: 1 }
      ),
      withRetry(
        () =>
          fetchApi<OverviewApiData>("/dashboard/xhs/overview?days=90", {
            next: { revalidate: 60 },
            timeoutMs: 1200
          }),
        { attempts: 1 }
      )
    ]);

    const overview = overviewResp.ok ? overviewResp.value : null;
    const lightTotals = totalsResp.ok ? totalsResp.value : null;
    const summary = {
      notes_total: Number(lightTotals?.notes_total ?? overview?.summary?.notes_total ?? parseMetricValue(xhsOverviewKpis[0]?.value)),
      creators_total: Number(lightTotals?.creators_total ?? overview?.summary?.creators_total ?? parseMetricValue(xhsOverviewKpis[1]?.value)),
      comments_total: Number(lightTotals?.comments_total ?? overview?.summary?.comments_total ?? parseMetricValue(xhsOverviewKpis[2]?.value)),
      notes_like_ge_100: Number(overview?.summary?.notes_like_ge_100 ?? parseMetricValue(xhsOverviewKpis[3]?.value))
    };

    const trend = overview?.trend ?? {};
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
        : fallbackTrendExplorer;

    const trends = (trend["7"] ?? []).map((item) => ({
      label: toMonthDayLabel(String(item.stat_date ?? item.date ?? "")),
      value: Number(item.new_count ?? 0)
    }));

    const liveIndustryRows = industriesResp.ok ? industriesResp.value.items ?? [] : [];
    const overviewIndustryRows = overview?.industries ?? [];
    const industriesFromLive = liveIndustryRows.map((item) => {
      const industryKey = String(item.industry_key ?? "");
      const industryName = String(item.industry_name ?? "");
      const meta = INDUSTRY_META[industryKey] ?? {
        zh: industryName,
        en: industryName,
        zhDesc: "行业数据观测",
        enDesc: "Industry data tracking"
      };
      return {
        industryKey,
        name: locale === "zh" ? meta.zh : meta.en,
        description: locale === "zh" ? meta.zhDesc : meta.enDesc,
        value: `${toLocaleCount(locale, Number(item.note_count ?? 0))} ${locale === "zh" ? "笔记" : "Notes"}`
      };
    });
    const industriesFromOverview = overviewIndustryRows
      .map((item) => {
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
          value: `${toLocaleCount(locale, Number(item.note_count ?? 0))} ${locale === "zh" ? "笔记" : "Notes"}`
        };
      })
      .slice(0, 12);
    const industries =
      (industriesFromLive.length ? industriesFromLive : industriesFromOverview.length ? industriesFromOverview : fallbackIndustries).slice(0, 12);

    const creators: CreatorOpportunityVM[] =
      (overview?.top_creators ?? []).slice(0, 20).map((item) => ({
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
      industries,
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
      aiCards: fallbackAiCards
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
      trendExplorer: fallbackTrendExplorer,
      industries: fallbackIndustries,
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
      aiCards: fallbackAiCards
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
        ? "relevance"
        : "stat";
  const sort =
    activeType === "creator"
      ? (["relevance", "followers", "notes", "sumStat"].includes(sortRaw) ? sortRaw : "relevance")
      : (["stat", "like", "read", "comments"].includes(sortRaw) ? sortRaw : "stat");
  const order = query?.order === "asc" ? "asc" : "desc";
  const inferredCategoryMode: "brand" | "category" =
    !industry && (/[A-Z0-9]/.test(keyword) || /[-_]/.test(keyword)) ? "brand" : "category";

  try {
    const size = 30;
    const requestTimeoutMs = 15000;
    const defaultPayload = createDefaultSearchPayload(page, size);

    const categoryRequest = () =>
      fetchApi<Record<string, unknown>>("/search/brand-category", {
        method: "POST",
        timeoutMs: requestTimeoutMs,
        body: JSON.stringify({
          query: keyword,
          mode: inferredCategoryMode,
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
        timeoutMs: requestTimeoutMs,
        body: JSON.stringify({
          query: keyword,
          industry,
          sort: activeType === "creator" ? sort : "relevance",
          order: activeType === "creator" ? order : "desc",
          page,
          size,
          include_notes: false,
          date_range: 30,
          freshness_hours: 24,
          force_refresh: false
        })
      });

    let pending: SearchPending | undefined;
    let categoryRaw: Record<string, unknown> = defaultPayload;
    let creatorRaw: Record<string, unknown> = defaultPayload;

    if (activeType === "creator") {
      const creatorResult = await withRetry(creatorRequest, { attempts: 1, retryDelayMs: 300 });
      if (creatorResult.ok) {
        creatorRaw = creatorResult.value;
      } else {
        const pendingByTimeout = isTimeoutOrAbortError(creatorResult.error);
        const upstreamMisconfigured = isUpstreamMisconfiguredError(creatorResult.error);
        creatorRaw = { ...defaultPayload, status: pendingByTimeout ? "pending" : "failed" };
        pending = { status: pendingByTimeout ? "pending" : "failed", type: "creator" };
        if (pendingByTimeout) {
          console.warn("[xhs-search] creator request timeout/abort after retry", {
            q: keyword,
            type: "creator",
            page,
            sort,
            order,
            errorName: getErrorName(creatorResult.error),
            errorMessage: getErrorMessage(creatorResult.error)
          });
        } else {
          console.error("[xhs-search] creator request failed after retry", {
            q: keyword,
            type: "creator",
            page,
            sort,
            order,
            errorType: upstreamMisconfigured ? "upstream_misconfigured" : "upstream_error",
            errorName: getErrorName(creatorResult.error),
            errorMessage: getErrorMessage(creatorResult.error)
          });
        }
      }
    } else {
      const categoryResult = await withRetry(categoryRequest, { attempts: 1, retryDelayMs: 300 });
      if (categoryResult.ok) {
        categoryRaw = categoryResult.value;
      } else {
        const pendingByTimeout = isTimeoutOrAbortError(categoryResult.error);
        const upstreamMisconfigured = isUpstreamMisconfiguredError(categoryResult.error);
        categoryRaw = { ...defaultPayload, status: pendingByTimeout ? "pending" : "failed" };
        pending = { status: pendingByTimeout ? "pending" : "failed", type: "category" };
        if (pendingByTimeout) {
          console.warn("[xhs-search] category request timeout/abort after retry", {
            q: keyword,
            type: "category",
            page,
            sort,
            order,
            industry,
            errorName: getErrorName(categoryResult.error),
            errorMessage: getErrorMessage(categoryResult.error)
          });
        } else {
          console.error("[xhs-search] category request failed after retry", {
            q: keyword,
            type: "category",
            page,
            sort,
            order,
            industry,
            errorType: upstreamMisconfigured ? "upstream_misconfigured" : "upstream_error",
            errorName: getErrorName(categoryResult.error),
            errorMessage: getErrorMessage(categoryResult.error)
          });
        }
      }
    }

    const resolveReadyPayload = (
      payload: Record<string, unknown>,
      type: "category" | "creator"
    ) => {
      const status = String(payload.status ?? "");
      if (status === "ready") {
        return payload;
      }

      if (status === "pending" || status === "running") {
        const jobId = String(payload.job_id ?? "");
        const pendingReasonRaw = payload.pending_reason;
        const pendingReason =
          typeof pendingReasonRaw === "string" && pendingReasonRaw.trim() ? pendingReasonRaw.trim() : undefined;
        const nextPollRaw = Number(payload.next_poll_after_ms ?? Number.NaN);
        const nextPollAfterMs = Number.isFinite(nextPollRaw) && nextPollRaw > 0 ? Math.round(nextPollRaw) : undefined;
        const freshnessRaw = Number(payload.data_freshness_seconds ?? Number.NaN);
        const dataFreshnessSeconds =
          Number.isFinite(freshnessRaw) && freshnessRaw >= 0 ? Math.round(freshnessRaw) : undefined;
        if (jobId && (!pending || pending.status !== "failed")) {
          pending = {
            status: "pending",
            type,
            jobId,
            pendingReason,
            nextPollAfterMs,
            dataFreshnessSeconds,
          };
        }
      }

      if (status === "failed" && !pending) {
        const pendingReasonRaw = payload.pending_reason;
        const pendingReason =
          typeof pendingReasonRaw === "string" && pendingReasonRaw.trim() ? pendingReasonRaw.trim() : undefined;
        pending = {
          status: "failed",
          type,
          pendingReason,
        };
      }

      return payload;
    };

    const activePayload = resolveReadyPayload(activeType === "creator" ? creatorRaw : categoryRaw, activeType);
    const searchSlice = buildSearchResultsSlice({
      locale,
      activeType,
      payload: activePayload,
      page,
      size
    });
    const categoryTotal = searchSlice.resultTotals.category;
    const creatorTotal = searchSlice.resultTotals.creator;
    const summaryResults = activeType === "creator" ? creatorTotal : categoryTotal;

    return {
      ...fallback,
      notes: searchSlice.notes,
      creators: searchSlice.creators,
      pending: searchSlice.pending ?? pending,
      resultTotals: searchSlice.resultTotals,
      searchSummary: searchSlice.searchSummary,
      summary: [
        { label: locale === "zh" ? "结果" : "Results", value: toLocaleCount(locale, summaryResults) },
        { label: locale === "zh" ? "达人" : "Creators", value: toLocaleCount(locale, searchSlice.searchSummary.creatorTotal) },
        { label: locale === "zh" ? "评论" : "Comments", value: toLocaleCount(locale, searchSlice.searchSummary.totalComments) },
        { label: locale === "zh" ? "品牌" : "Brands", value: "-" }
      ],
      filters: [
        { label: locale === "zh" ? "搜索" : "Query", value: keyword, active: true },
        { label: locale === "zh" ? "排序" : "Sort", value: locale === "zh" ? "按互动" : "By Engagement" },
        { label: locale === "zh" ? "时间窗" : "Window", value: locale === "zh" ? "近 30 天" : "Last 30 Days" }
      ]
    };
  } catch (error) {
    await wait();
    const timeoutOrAbort = isTimeoutOrAbortError(error);
    if (!timeoutOrAbort) {
      console.error("[xhs-search] unexpected search workbench failure", {
        q: keyword,
        type: activeType,
        page,
        sort,
        order,
        industry,
        errorName: getErrorName(error),
        errorMessage: getErrorMessage(error)
      });
    }
    return {
      ...fallback,
      searchSummary: {
        noteTotal: 0,
        creatorTotal: 0,
        totalComments: 0
      },
      pending: {
        status: timeoutOrAbort ? "pending" : "failed",
        type: activeType,
        pendingReason: timeoutOrAbort ? "timeout" : "upstream_failed",
      }
    };
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
