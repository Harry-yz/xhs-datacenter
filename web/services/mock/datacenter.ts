import {
  type AudienceProfileVM,
  type BrandDetailVM,
  type BrandRankingItem,
  type CategoryDetailVM,
  type CreatorOpportunityVM,
  type DashboardKPI,
  type HotCategoryVM,
  type IndustryCardVM,
  type NoteAnalysisCardVM,
  type NoteDetailVM,
  type PlatformCardVM,
  type SearchWorkbenchVM,
  type TrendPoint
} from "@/types/datacenter";

const xhsNotes = "31,785";
const xhsCreators = "802";
const xhsComments = "12,583";
const xhsHighValue = "2,757";

export const platformCards: PlatformCardVM[] = [
  {
    platform: "Xiaohongshu",
    description: "Beauty / Lifestyle / Creator Signals",
    notes: xhsNotes,
    creators: xhsCreators,
    href: "/datacenter/xhs",
    status: "available",
    gradient:
      "linear-gradient(132deg, rgba(255,198,154,0.96) 0%, rgba(255,140,182,0.94) 46%, rgba(190,124,255,0.92) 78%, rgba(114,141,255,0.9) 100%)"
  },
  {
    platform: "Douyin",
    description: "Short Video / Trend / Amplification",
    notes: "18,420",
    creators: "642",
    status: "coming-soon",
    gradient:
      "linear-gradient(132deg, rgba(255,190,149,0.95) 0%, rgba(255,130,176,0.94) 45%, rgba(182,121,255,0.91) 76%, rgba(108,135,250,0.89) 100%)"
  },
  {
    platform: "TikTok",
    description: "Global / Consumer / Creator Signals",
    notes: "12,160",
    creators: "458",
    status: "coming-soon",
    gradient:
      "linear-gradient(130deg, rgba(255,204,161,0.95) 0%, rgba(255,146,188,0.93) 48%, rgba(193,133,255,0.9) 77%, rgba(118,147,255,0.88) 100%)"
  },
  {
    platform: "Instagram",
    description: "Visual / Premium / Brand Mood",
    notes: "9,840",
    creators: "374",
    status: "coming-soon",
    gradient:
      "linear-gradient(134deg, rgba(255,196,154,0.95) 0%, rgba(255,138,180,0.93) 44%, rgba(188,128,252,0.9) 75%, rgba(113,143,248,0.88) 100%)"
  },
  {
    platform: "Facebook",
    description: "Community / Demand / Discussion Depth",
    notes: "6,912",
    creators: "221",
    status: "coming-soon",
    gradient:
      "linear-gradient(133deg, rgba(255,202,165,0.95) 0%, rgba(255,143,184,0.92) 47%, rgba(186,129,248,0.9) 76%, rgba(116,149,252,0.87) 100%)"
  },
  {
    platform: "Twitter",
    description: "Realtime / Opinion / Trend Signals",
    notes: "8,276",
    creators: "309",
    status: "coming-soon",
    gradient:
      "linear-gradient(132deg, rgba(255,194,152,0.95) 0%, rgba(255,136,178,0.93) 46%, rgba(181,123,246,0.9) 74%, rgba(109,141,248,0.88) 100%)"
  }
];

export const xhsOverviewKpis: DashboardKPI[] = [
  { label: "Notes", value: xhsNotes, change: "+14.2%" },
  { label: "Creators", value: xhsCreators, change: "+9.4%" },
  { label: "Comments", value: xhsComments, change: "+11.7%" },
  { label: "100+ Posts", value: xhsHighValue, change: "+18.6%", tone: "accent" }
];

export const xhsTrend: TrendPoint[] = [
  { label: "03/19", value: 820 },
  { label: "03/20", value: 1080 },
  { label: "03/21", value: 1220 },
  { label: "03/22", value: 1375 },
  { label: "03/23", value: 1480 },
  { label: "03/24", value: 1720 },
  { label: "03/25", value: 1910 }
];

export const xhsIndustries: IndustryCardVM[] = [
  { name: "Beauty", description: "Content, creators, and brand signals", value: "31.7K Notes" },
  { name: "Mother & Baby", description: "Product trust and recommendation loops", value: "8.2K Notes" },
  { name: "Fashion", description: "Outfit references and brand mentions", value: "10.8K Notes" },
  { name: "Food", description: "Taste, recipe, and scene-driven posts", value: "9.4K Notes" },
  { name: "Travel", description: "Destination planning and guide demand", value: "7.2K Notes" },
  { name: "Home", description: "Decor inspiration and utility content", value: "6.9K Notes" },
  { name: "Digital", description: "Device evaluation and lifestyle utility", value: "5.8K Notes" },
  { name: "Fitness", description: "Routine, efficiency, and body management", value: "4.7K Notes" },
  { name: "Pets", description: "Care, products, and emotional connection", value: "4.3K Notes" },
  { name: "Education", description: "Learning efficiency and career intent", value: "3.8K Notes" },
  { name: "Automotive", description: "Lifestyle ownership and upgrade behavior", value: "2.9K Notes" },
  { name: "Luxury", description: "Premium desire and purchase confidence", value: "2.4K Notes" }
];

export const hotCategories: HotCategoryVM[] = [
  { slug: "sunscreen", name: "防晒", description: "通勤、户外、防晒力", notes: "8.6K Notes", change: "+12%" },
  { slug: "foundation", name: "底妆", description: "遮瑕、服帖、持妆", notes: "6.1K Notes", change: "+8%" },
  { slug: "serum", name: "精华", description: "修护、提亮、功效感", notes: "5.4K Notes", change: "+15%" },
  { slug: "setting", name: "定妆", description: "控油、细腻、通勤", notes: "4.8K Notes", change: "+11%" },
  { slug: "cleanser", name: "卸妆清洁", description: "温和、清洁力、敏感肌", notes: "3.9K Notes", change: "+6%" },
  { slug: "lip", name: "唇部彩妆", description: "色号、显白、氛围感", notes: "3.4K Notes", change: "+9%" }
];

export const brandRanking: BrandRankingItem[] = [
  { slug: "lancome", brandName: "兰蔻", engagementTotal: "72.5K", creatorCount: "329", contentCount: "515", trendDelta: "+12%" },
  { slug: "ysl", brandName: "YSL", engagementTotal: "71.3K", creatorCount: "249", contentCount: "412", trendDelta: "+18%" },
  { slug: "estee-lauder", brandName: "雅诗兰黛", engagementTotal: "100.2K", creatorCount: "261", contentCount: "364", trendDelta: "+9%" },
  { slug: "skinceuticals", brandName: "修丽可", engagementTotal: "58.1K", creatorCount: "266", contentCount: "305", trendDelta: "+14%" }
];

export const creatorOpportunities: CreatorOpportunityVM[] = [
  { name: "惊喜盒子", followers: "1.45M", direction: "成分测评 / 质地对比", cpe: "0.18" },
  { name: "小石頭", followers: "1.39M", direction: "高频种草 / 通勤场景", cpe: "0.21" },
  { name: "是阿束啊", followers: "1.42M", direction: "底妆评测 / 平价替代", cpe: "0.16" }
];

export const noteCards: NoteAnalysisCardVM[] = [
  {
    noteId: "69b9a5d7000000002102f38d",
    coverColor: "from-[#f7c7b8] via-[#f1b8d6] to-[#a7d8ff]",
    title: "拯救垮脸｜静姐这套手法够我用一辈子",
    author: "惊喜盒子",
    followers: "1.45M",
    likeCount: "38,303",
    collectionCount: "68,574",
    commentCount: "179",
    tags: ["#紧致提拉", "#美妆手法", "#氛围感妆容"],
    aiLabels: ["#情绪共鸣", "#高收藏表达", "#强复刻意图"]
  },
  {
    noteId: "69aa2ad7000000001d01d565",
    coverColor: "from-[#f5d29d] via-[#f1c1cf] to-[#bfdef5]",
    title: "一次“破产”的化妆体验",
    author: "是阿束啊",
    followers: "1.42M",
    likeCount: "261,093",
    collectionCount: "90,609",
    commentCount: "3,592",
    tags: ["#底妆", "#大牌体验", "#妆感对比"],
    aiLabels: ["#高互动话题", "#评论爆发", "#品牌心智强"]
  },
  {
    noteId: "69c1fa3700000000120088ef",
    coverColor: "from-[#a7dbdb] via-[#b9dcff] to-[#e6caff]",
    title: "有没有适合穷人的卸妆油啊",
    author: "小石頭",
    followers: "1.39M",
    likeCount: "12,420",
    collectionCount: "18,614",
    commentCount: "2,046",
    tags: ["#卸妆", "#平价替代", "#敏感肌"],
    aiLabels: ["#价格敏感", "#强需求讨论", "#平替策略"]
  }
];

export const audienceProfiles: AudienceProfileVM = {
  ageDistribution: [
    { label: "18岁以下", value: 3.5 },
    { label: "18-24岁", value: 31.2 },
    { label: "25-34岁", value: 57.0 },
    { label: "35-44岁", value: 7.2 },
    { label: "44岁以上", value: 1.1 }
  ],
  genderDistribution: [
    { label: "男性", value: 5.6 },
    { label: "女性", value: 94.4 }
  ]
};

export const searchWorkbench: SearchWorkbenchVM = {
  summary: [
    { label: "Results", value: "842" },
    { label: "Creators", value: "196" },
    { label: "Comments", value: "5,760" },
    { label: "Brands", value: "18" }
  ],
  filters: [
    { label: "Query", value: "防晒" },
    { label: "Min Likes", value: "1000+" },
    { label: "Min Saves", value: "500+" },
    { label: "Sort", value: "By Engagement", active: true },
    { label: "Window", value: "Last 7 Days" }
  ],
  statusStats: [
    { label: "Content Velocity", value: "+18.6%", helper: "vs previous 7 days" },
    { label: "Save Bias", value: "1.74x", helper: "save-to-comment ratio" },
    { label: "High Value Share", value: "16%", helper: "1000+ like posts" }
  ],
  trends: xhsTrend,
  categoryDistribution: [
    { label: "防晒", value: 36 },
    { label: "底妆", value: 22 },
    { label: "精华", value: 16 },
    { label: "定妆", value: 14 },
    { label: "其他", value: 12 }
  ],
  engagementBands: [
    { label: "100-499", value: 34 },
    { label: "500-999", value: 28 },
    { label: "1000-4999", value: 22 },
    { label: "5000+", value: 16 }
  ],
  contentTypes: [
    { label: "图文", value: 68 },
    { label: "视频", value: 32 }
  ],
  notes: noteCards,
  creators: creatorOpportunities,
  aiDecisionCards: [
    { title: "高频痛点", points: ["油皮通勤场景仍然最强", "搓泥、假白、闷痘是反复出现的问题"] },
    { title: "有效卖点", points: ["成膜快、防水、不拔干表现最好", "真实肤感对比比单纯参数更能拉动收藏"] },
    { title: "行动建议", points: ["优先布局通勤防晒内容", "用对比式封面强化收藏动机"] }
  ]
};

export const categoryDetail: CategoryDetailVM = {
  breadcrumb: ["小红书", "美妆", "防晒"],
  heroSummary: "Outdoor, commute, and oil-control claims are driving this category.",
  filters: [
    { label: "Category", value: "防晒", active: true },
    { label: "Window", value: "Last 30 Days" },
    { label: "Content Quality", value: "100+ Likes" }
  ],
  statusStats: [
    { label: "Scenario Heat", value: "Commute / Outdoor", helper: "dominant save context" },
    { label: "Claim Shift", value: "Fast Film Set", helper: "highest gain selling point" },
    { label: "Demand Signal", value: "Oil-Control", helper: "strongest comment theme" }
  ],
  kpis: [
    { label: "内容量", value: "8.6K", change: "+12%" },
    { label: "高价值内容", value: "742", change: "+18%" },
    { label: "达人覆盖", value: "219", change: "+9%" }
  ],
  trend: xhsTrend,
  opportunityCards: [
    { title: "热点场景", value: "通勤 / 户外", description: "Morning commute and travel continue to dominate saves and shares." },
    { title: "上升诉求", value: "防水 / 成膜快", description: "Fast set and no white cast language is trending up in high-performing posts." },
    { title: "建议切入", value: "油皮通勤", description: "Build a creator angle around high-heat, long-wear routines." }
  ],
  needs: [
    { title: "Pain Points", tags: ["搓泥", "假白", "闷痘", "泛油"] },
    { title: "Selling Points", tags: ["成膜快", "防水", "不拔干", "持妆"] },
    { title: "Scenarios", tags: ["早八通勤", "军训", "海边度假", "户外运动"] }
  ],
  brands: brandRanking,
  topNotes: noteCards,
  commentInsights: {
    summary: ["用户最怕假白和闷痘", "高收藏内容往往明确解决通勤和油皮问题", "评论里对质地和回购意愿表达很强"],
    comments: ["通勤一天都没怎么出油，真的很能打。", "求真实油皮使用感，不想再买假白的了。", "成膜速度快到我愿意回购，收藏了。"]
  },
  creators: creatorOpportunities
};

export const brandDetail: BrandDetailVM = {
  breadcrumb: ["小红书", "美妆", "YSL"],
  filters: [
    { label: "Brand", value: "YSL", active: true },
    { label: "Window", value: "Last 30 Days" },
    { label: "Sort", value: "By Engagement" }
  ],
  statusStats: [
    { label: "Share of Voice", value: "12.4%", helper: "within tracked beauty brands" },
    { label: "Creator Spread", value: "249", helper: "distinct creator coverage" },
    { label: "Save Intention", value: "High", helper: "content skews toward save-heavy formats" }
  ],
  kpis: [
    { label: "内容量", value: "412", change: "+10%" },
    { label: "达人覆盖", value: "249", change: "+7%" },
    { label: "互动总量", value: "71.3K", change: "+18%", tone: "accent" },
    { label: "高价值内容", value: "146", change: "+13%" }
  ],
  trend: xhsTrend,
  competitors: [
    { label: "YSL", value: 71 },
    { label: "兰蔻", value: 72 },
    { label: "雅诗兰黛", value: 100 },
    { label: "修丽可", value: 58 }
  ],
  categoryMix: [
    { label: "底妆", value: 42 },
    { label: "唇部", value: 31 },
    { label: "定妆", value: 15 },
    { label: "其他", value: 12 }
  ],
  audience: audienceProfiles,
  topNotes: noteCards,
  feedback: {
    positive: ["高级感和品牌辨识度强", "彩妆色号讨论热度高", "内容收藏率稳定偏高"],
    caution: ["价格门槛高", "部分产品对肤质适配讨论分化明显"],
    rawComments: ["气垫妆感是真的高级，但价格也是真的不低。", "黑管色号太绝了，显白这一点评论区几乎一致。", "希望能多看到不同肤质的真实反馈。"]
  },
  aiDecisions: [
    { title: "品牌优势", points: ["色号和高级感表达强", "品牌心智高，适合做形象向内容"] },
    { title: "用户顾虑", points: ["价格敏感明显", "肤质适配信息仍需补强"] },
    { title: "建议方向", points: ["强化不同肤质场景评测", "用更明确的妆效对比拉升收藏与转发"] }
  ]
};

export const noteDetail: NoteDetailVM = {
  noteId: noteCards[0].noteId,
  title: noteCards[0].title,
  author: noteCards[0].author,
  publishTime: "2026-03-24 22:32",
  category: "底妆",
  brand: "YSL",
  statusStats: [
    { label: "Hook Pattern", value: "Before / After", helper: "drives strongest save intent" },
    { label: "Audience Signal", value: "High Replication", helper: "tutorial-style comments dominate" },
    { label: "Content Type", value: "Technique Explain", helper: "better than pure product pitch" }
  ],
  tags: ["#紧致提拉", "#底妆手法", "#妆容技巧"],
  metrics: [
    { label: "点赞", value: "38,303" },
    { label: "收藏", value: "68,574" },
    { label: "评论", value: "179" },
    { label: "阅读", value: "1,100,085" }
  ],
  content: "通过手法调整面中和轮廓，结合轻薄底妆与提亮方式，在不厚重的前提下放大精致感与立体度。",
  aiBreakdown: [
    { title: "Pain Points", tags: ["垮脸感", "面中凹陷", "底妆不立体"] },
    { title: "Selling Points", tags: ["上脸精致", "手法可复刻", "效果对比强"] },
    { title: "Scenarios", tags: ["约会妆", "通勤妆", "拍照妆"] },
    { title: "Sentiment", tags: ["惊艳", "想复刻", "强收藏"] }
  ],
  commentInsight: {
    aiSummary: ["评论区核心反馈是‘想学会这套手法’。", "用户对妆前后轮廓变化最敏感。", "收藏行为远强于评论，说明教程复用价值高。"],
    rawComments: ["这套手法真的有救命感，我先收藏。", "终于明白面中提亮该怎么做了。", "求更详细的步骤分解，这个我一定要学。"]
  },
  strategyTakeaways: ["强对比视觉是首因", "教程式结构强化收藏", "更适合用在高复刻意图的底妆内容里"]
};
