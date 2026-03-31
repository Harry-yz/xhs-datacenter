# Oran Data Center 前端设计说明

## 1. 项目定位

本项目是 `Oran Data Center` 的前端第一版，目标不是做一个普通后台，而是做一个带品牌感的数据中心入口。

当前阶段的定位已经明确：

- 首页负责品牌入口与六平台数据入口
- 小红书是唯一先做深的平台
- 二级页先像 BI 驾驶舱
- 三级页先给数据视图，再给 AI 营销决策
- 整体使用 mock-first 方式开发，后续逐步切换真实数据接口

## 2. 技术栈与工程结构

前端单独放在仓库内的 `web/` 目录，采用：

- `Next.js 14` + `App Router`
- `React 18`
- `TypeScript`
- `Tailwind CSS`
- `next-themes`
- `Zustand` 仅管理 UI 状态

目录结构：

- `web/app/`：路由页面与布局
- `web/components/`：通用组件和数据中台组件
- `web/layouts/`：页面壳层
- `web/services/`：mock 数据适配层和后续真实接口层
- `web/types/`：页面 view model 类型
- `web/config/`：环境配置、字典、metadata
- `web/store/`：仅 UI 状态
- `web/utils/`：路由和格式化工具
- `web/middleware.ts`：登录态保护

## 3. 当前路由框架

当前已经落地的页面结构如下：

- `/<lang>/datacenter`
- `/<lang>/datacenter/xhs`
- `/<lang>/datacenter/xhs/search`
- `/<lang>/datacenter/xhs/category/[slug]`
- `/<lang>/datacenter/xhs/brand/[slug]`
- `/<lang>/datacenter/xhs/note/[noteId]`
- `/<lang>/login`

支持语言：

- `zh`
- `en`

路由规则：

- 公开页可直接访问
- 深层分析页通过 `middleware` 做登录保护

## 4. 视觉基调

### 4.1 总体气质

当前视觉方向已经调整为：

- 浅色优先，不再默认黑底
- 低饱和粉、杏、蓝、薄荷、淡紫渐变
- 大圆角、细边框、轻玻璃感
- 文字更克制，信息密度更高
- 动效以 hover、opacity、translate 为主

### 4.2 明暗主题

- 默认进入 `light`
- `dark` 不再是纯黑，而是柔和夜间版
- 两套主题保持相同层级结构和组件排布

### 4.3 首页卡片色彩策略

六张平台卡都使用完整渐变背景，不再通过“未开放”做黑色占位。

当前约束：

- 六张卡都要像“已经完成”
- 只有小红书可点击
- 其余五张不可点击，但视觉上与小红书保持同完成态
- 卡片内文案尽量少，方便中英切换

## 5. 多语言规则

当前多语言规范已经确定：

- 中文页面显示平台中文名
- 英文页面显示平台英文名
- 页面 chrome、导航、模块标题、按钮都必须双语
- 原始内容数据可保留中文原文

平台命名规范：

- 中文：`小红书 / 抖音 / 抖音海外版`
- 英文：`XiaoHongShu / Douyin / TikTok`
- 其余平台统一为：`Instagram / Facebook / Twitter`

## 6. 页面框架

### 6.1 首页 `/<lang>/datacenter`

页面职责：

- 展示品牌感
- 展示六平台入口
- 用最少文字建立数据中心印象

当前结构：

1. 顶部导航
2. 首页标题区
3. 六平台卡片墙

具体说明：

- 顶部导航包含品牌、语言切换、主题切换、登录
- 首页标题区保留完整 `Oran Data Center`，但整体明显缩小，不再压缩下方六张卡片
- 六平台区域采用 `3 x 2` 网格
- 每张卡只展示：
  - 平台名
  - 一句短描述
  - `Notes / Creators`
  - 淡化的 `Oran AI`
- 五张未开放平台与小红书保持同样的完成态视觉，只是不可点击
- 首页卡片不再显示任何 `已开放 / 即将开放 / coming soon` 状态提示

首页原则：

- 不写长段 Hero 文案
- 不单独做小红书预览区
- 不做过多 CTA

### 6.2 小红书二级页 `/<lang>/datacenter/xhs`

页面职责：

- 先做 BI 驾驶舱
- 再做 AI 营销判断入口

当前结构：

1. 顶部导航
2. 页面工具条
3. 首屏总览 Hero
4. BI 视图区
5. 行业矩阵
6. 美妆热点品类
7. 品牌榜单 + 趋势
8. 爆文洞察
9. AI 营销决策

页面工具条包含：

- 返回首页按钮
- 顶部搜索框

首屏 Hero：

- 左侧只保留 `Data Center` 与平台标签
- 右侧保留 `2 x 2 KPI`
  - `Notes`
  - `Creators`
  - `Comments`
  - `100+ Posts`

BI 视图区：

- 内容走势主图
- 热点品类占比
- 品牌互动占比

已删除模块：

- `观察重点`
- `数据就绪度`

原因：

- 这两块信息偏说明文字，不像数据视图
- 会让二级页首屏显得空

### 6.3 搜索工作台 `/<lang>/datacenter/xhs/search`

页面职责：

- 查询后先看数据面板
- 再看具体内容
- 最后看 AI 决策

当前结构：

1. 顶部导航
2. 页面工具条
3. 首屏 Hero
4. 查询筛选条
5. Query Summary
6. 状态统计条
7. 数据图表区
8. 笔记结果流
9. AI 决策区

页面工具条包含：

- 返回小红书页
- 顶部搜索框

数据图表区包括：

- 结果走势
- 品类分布
- 互动区间
- 内容类型

### 6.4 品类页 `/<lang>/datacenter/xhs/category/[slug]`

页面职责：

- 解释这个品类有没有机会
- 告诉品牌方该怎么做内容

当前结构：

1. 顶部导航
2. 返回按钮
3. Hero
4. 筛选条
5. 状态统计条
6. 品类趋势 + 机会卡
7. 需求层
8. 品牌榜 + 爆文
9. AI 机会摘要 / 评论 / 达人机会

Hero 重点：

- 路径面包屑
- 品类一句话结论
- 三个强 KPI

### 6.5 品牌页 `/<lang>/datacenter/xhs/brand/[slug]`

页面职责：

- 看品牌竞争
- 看品牌人群
- 看品牌内容表现

当前结构：

1. 顶部导航
2. 返回按钮
3. Hero
4. 筛选条
5. 状态统计条
6. 品牌趋势 + 竞品对比
7. 人群画像
8. 高价值内容
9. 评论反馈
10. AI 建议

人群画像首版只保留：

- 年龄分布
- 性别分布

暂不放：

- 城市层级
- 兴趣偏好

### 6.6 笔记详情页 `/<lang>/datacenter/xhs/note/[noteId]`

页面职责：

- 拆解一篇内容为什么有效
- 让用户看懂这篇内容的可复用价值

当前结构：

1. 顶部导航
2. 返回按钮
3. 封面与基础信息
4. 互动指标
5. 状态统计条
6. 内容视图 + AI 拆解
7. 评论摘要 + 代表评论
8. 可复用营销启发

## 7. 当前组件层级

核心组件已经形成一套数据中台组件层：

- `SiteHeader`
- `PageShell`
- `PageToolbar`
- `DashboardHero`
- `MetricCard`
- `PlatformCard`
- `MiniAreaChart`
- `DistributionBars`
- `BrandRankingPanel`
- `IndustryCard`
- `HotCategoryCard`
- `NoteAnalysisCard`
- `StatusOverviewStrip`
- `InsightBlock`
- `StackedAudienceBars`

这些组件的职责已经比较明确：

- 入口页用 `PlatformCard`
- BI 页用 `MetricCard / MiniAreaChart / DistributionBars / BrandRankingPanel`
- 内容分析页用 `NoteAnalysisCard / InsightBlock`
- 顶部结构统一交给 `SiteHeader + PageToolbar + DashboardHero`

## 8. 当前实现边界

### 8.1 已经完成的部分

- 首页六平台卡片墙
- 小红书二级页
- 搜索工作台
- 品类页
- 品牌页
- 笔记详情页
- 中英双语基础框架
- 明暗主题切换
- mock-first 数据层

### 8.2 当前仍按 mock 驱动的部分

- 品牌趋势更细颗粒度数据
- AI 决策区的结构化内容
- 更复杂的人群画像
- 更完整的竞品对比逻辑

### 8.3 后续真实接口接入方向

- 首页卡片统计量接真实接口
- 小红书二级页 KPI 和趋势接真实接口
- 搜索工作台接统一查询接口
- 品牌页和品类页接真实聚合层
- 评论、品牌、人群画像逐步替换 mock 字段

## 9. 当前页面优化方向

本轮之后，前端页面接下来继续优化的重点是：

1. 首页六卡的渐变层次再提升一版
2. 二级页首屏图表密度继续增加
3. 二三级页的返回和搜索交互再细化
4. 英文页的原始中文内容是否要做解释层
5. mock 数据与真实接口的 view model 对齐

## 10. 结论

当前页面框架已经稳定成以下模式：

- 首页：品牌入口页
- 二级页：BI 驾驶舱
- 三级搜索页：数据工作台
- 品类页：机会页
- 品牌页：竞争与人群页
- 笔记详情页：内容拆解页

这份文档从现在开始作为页面结构和视觉层级的中文基线说明，后续所有页面调整都以它为准继续收口。
