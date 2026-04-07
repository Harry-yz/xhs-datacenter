export type MetricValue = {
  label: string;
  value: string;
  change?: string;
};

export type FilterChip = {
  label: string;
  value: string;
  active?: boolean;
};

export type StatusStat = {
  label: string;
  value: string;
  helper?: string;
};

export type PlatformCardVM = {
  platform: string;
  description: string;
  notes: string;
  creators: string;
  href?: string;
  status: "available" | "coming-soon";
  gradient: string;
};

export type TrendPoint = {
  label: string;
  value: number;
};

export type TrendWindow = 7 | 30 | 90;

export type TrendSeriesPoint = {
  date: string;
  value: number;
};

export type TrendExplorerVM = {
  metricKey: "daily_new_notes";
  metricLabel: string;
  defaultWindow: TrendWindow;
  windows: Record<TrendWindow, TrendSeriesPoint[]>;
};

export type XhsLiveMetrics = {
  newNotes24h: number;
  updatedNotes30m: number;
  newComments30m: number;
  jobsRunning: number;
  generatedAt: string;
};

export type XhsLiveTotals = {
  notesTotal: number;
  creatorsTotal: number;
  commentsTotal: number;
  generatedAt: string;
};

export type DashboardKPI = {
  label: string;
  value: string;
  change?: string;
  tone?: "default" | "accent";
};

export type IndustryCardVM = {
  industryKey?: string;
  name: string;
  description: string;
  value: string;
  highlighted?: boolean;
};

export type HotCategoryVM = {
  slug: string;
  name: string;
  description: string;
  notes: string;
  change: string;
};

export type BrandRankingItem = {
  slug: string;
  brandName: string;
  engagementTotal: string;
  creatorCount: string;
  contentCount: string;
  trendDelta: string;
};

export type CreatorOpportunityVM = {
  authorId?: string;
  name: string;
  followers: string;
  followersValue?: number;
  direction: string;
  cpe: string;
  notesCount?: number;
  totalInteractions?: number;
  profileUrl?: string;
};

export type NoteAnalysisCardVM = {
  noteId: string;
  coverColor: string;
  title: string;
  author: string;
  followers: string;
  likeCount: string;
  likeCountValue?: number;
  collectionCount: string;
  collectionCountValue?: number;
  commentCount: string;
  commentCountValue?: number;
  readCount?: number;
  interactionTotal?: number;
  tags: string[];
  aiLabels: string[];
};

export type AudienceProfileVM = {
  ageDistribution: Array<{ label: string; value: number }>;
  genderDistribution: Array<{ label: string; value: number }>;
};

export type SearchWorkbenchVM = {
  summary: MetricValue[];
  filters: FilterChip[];
  statusStats: StatusStat[];
  trends: TrendPoint[];
  categoryDistribution: Array<{ label: string; value: number }>;
  engagementBands: Array<{ label: string; value: number }>;
  contentTypes: Array<{ label: string; value: number }>;
  notes: NoteAnalysisCardVM[];
  creators: CreatorOpportunityVM[];
  searchSummary?: {
    noteTotal: number;
    creatorTotal: number;
    totalComments: number;
  };
  pending?: {
    status: "pending" | "failed";
    type: "category" | "creator";
    jobId?: string;
    pendingReason?: string;
    nextPollAfterMs?: number;
    dataFreshnessSeconds?: number;
  };
  resultTotals?: {
    category: number;
    creator: number;
    page: number;
    size: number;
    categoryHasMore?: boolean;
    creatorHasMore?: boolean;
    categoryTotalIsEstimate?: boolean;
    creatorTotalIsEstimate?: boolean;
  };
  aiDecisionCards: Array<{ title: string; points: string[] }>;
};

export type SearchResultsSliceVM = {
  notes: NoteAnalysisCardVM[];
  creators: CreatorOpportunityVM[];
  searchSummary: {
    noteTotal: number;
    creatorTotal: number;
    totalComments: number;
  };
  pending?: {
    status: "pending" | "failed";
    type: "category" | "creator";
    jobId?: string;
    pendingReason?: string;
    nextPollAfterMs?: number;
    dataFreshnessSeconds?: number;
  };
  resultTotals: {
    category: number;
    creator: number;
    page: number;
    size: number;
    categoryHasMore?: boolean;
    creatorHasMore?: boolean;
    categoryTotalIsEstimate?: boolean;
    creatorTotalIsEstimate?: boolean;
  };
};

export type CategoryDetailVM = {
  breadcrumb: string[];
  heroSummary: string;
  filters: FilterChip[];
  statusStats: StatusStat[];
  kpis: DashboardKPI[];
  trend: TrendPoint[];
  opportunityCards: Array<{ title: string; value: string; description: string }>;
  needs: Array<{ title: string; tags: string[] }>;
  brands: BrandRankingItem[];
  topNotes: NoteAnalysisCardVM[];
  commentInsights: {
    summary: string[];
    comments: string[];
  };
  creators: CreatorOpportunityVM[];
};

export type BrandDetailVM = {
  breadcrumb: string[];
  filters: FilterChip[];
  statusStats: StatusStat[];
  kpis: DashboardKPI[];
  trend: TrendPoint[];
  competitors: Array<{ label: string; value: number }>;
  categoryMix: Array<{ label: string; value: number }>;
  audience: AudienceProfileVM;
  topNotes: NoteAnalysisCardVM[];
  feedback: {
    positive: string[];
    caution: string[];
    rawComments: string[];
  };
  aiDecisions: Array<{ title: string; points: string[] }>;
};

export type NoteDetailVM = {
  noteId: string;
  title: string;
  author: string;
  publishTime: string;
  category: string;
  brand: string;
  statusStats: StatusStat[];
  tags: string[];
  metrics: DashboardKPI[];
  content: string;
  aiBreakdown: Array<{ title: string; tags: string[] }>;
  commentInsight: {
    aiSummary: string[];
    rawComments: string[];
  };
  strategyTakeaways: string[];
};
