# 小红书数据中台智能报告 Agent 架构与协作图

版本：v1.0  
文档类型：架构图 / Agent 协作图 / 面试展示材料  
项目名称：小红书数据中台智能报告 Agent  
日期：2026-04-29

## 1. 产品总架构图

```mermaid
flowchart TB
    U[用户 / PM / 销售顾问 / 品牌运营] --> FE[小红书数据中台前端<br/>Next.js 数据中心]
    U --> CLI[报告生成 CLI<br/>brand/category/products/competitors/window]

    FE --> API[FastAPI 查询服务<br/>搜索 / 看板 / 详情 / 健康检查]
    API --> TASK[Celery + Redis 异步采集任务]
    TASK --> CALLBACK[采集回调与入库服务]
    CALLBACK --> DB[(PostgreSQL<br/>笔记 / 作者 / 评论 / 搜索词 / 品牌关系 / 竞品指标)]
    API --> DB

    CLI --> PIPE[ReportPipeline<br/>报告生成入口]
    FE -.未来接入.-> PIPE

    PIPE --> SCOUT[DataScoutAgent<br/>只读 SQL 取数]
    SCOUT --> DB
    SCOUT --> EVIDENCE[EvidencePack<br/>全量指标 + 抽样证据 + 数据质量]

    EVIDENCE --> GRAPH[LangGraph StateGraph<br/>多 Agent 编排]
    GRAPH --> JSON[Report JSON<br/>结构化报告资产]
    GRAPH --> MD[Markdown 报告]
    GRAPH --> HTML[Premium HTML 报告]

    JSON --> LIB[报告库 / 前端报告页 / 后续追踪]
    MD --> DOC[飞书 / Notion / 面试材料]
    HTML --> SALES[售前提案 / 客户演示]
```

这张图的表达重点：数据中台负责采集、存储、搜索和看板；智能报告 Agent 负责把数据资产转成洞察资产。两者组合后，产品从“数据可查”升级为“结论可交付”。

## 2. Agent 协作流程图

```mermaid
flowchart LR
    START([输入品牌 brief]) --> A[DataScoutAgent<br/>构建证据包]
    A --> B[Evidence Compressor<br/>压缩 LLM 输入证据]
    B --> C[ExternalContextScoutAgent<br/>补充平台/品类/品牌背景]
    C --> D[MetricAnalystAgent<br/>六维健康度评分]
    D --> E[ContentInsightAgent<br/>内容主题/爆文模式/关键词机会]
    D --> F[AudienceInsightAgent<br/>受众分层/动机/痛点/场景]
    E --> G[DiagnosisAgent<br/>综合诊断与 90 天动作]
    F --> G
    G --> H[FactCheckAgent<br/>事实校验/降级/免责声明]
    H --> I[ReportDataComposer<br/>统一结构化 JSON]
    I --> J[ExecutiveEditorAgent<br/>管理层摘要与主叙事]
    J --> K[SectionWriterAgent<br/>章节化报告写作]
    K --> L[HtmlRenderer<br/>HTML 渲染]
    K --> M[MarkdownRenderer<br/>Markdown 渲染]
    L --> END([输出 HTML / Markdown / JSON])
    M --> END
```

协作设计的核心是“先结构化分析，再编辑表达”。指标、内容、受众和诊断节点分别产出结构化结果，FactCheckAgent 负责守住可信边界，最后再进入总编和章节写作。

## 3. LangGraph 编排图

```mermaid
stateDiagram-v2
    [*] --> data_scout
    data_scout --> evidence_compressor
    evidence_compressor --> external_context
    external_context --> metric_analyst
    metric_analyst --> content_insight
    metric_analyst --> audience_insight
    content_insight --> diagnosis
    audience_insight --> diagnosis
    diagnosis --> fact_check
    fact_check --> report_data_composer
    report_data_composer --> executive_editor
    executive_editor --> section_writer
    section_writer --> html_renderer
    html_renderer --> finalize
    finalize --> [*]
```

项目使用 LangGraph `StateGraph` 编排，状态对象是 `ReportState`。每个节点只读上一阶段必要字段，并向 state 写入自己的结构化产物。当前链路以确定顺序为主，但内容洞察和受众洞察在产品逻辑上是并行分支，未来可进一步异步化。

## 4. 数据流与证据链

```mermaid
flowchart TB
    INPUT[Brand Brief<br/>品牌 / 品类 / 核心产品 / 竞品 / 时间窗] --> TERMS[品牌词与产品词扩展]
    TERMS --> SQL[只读 SQL 查询<br/>索引优先召回]

    SQL --> FULL[全量聚合指标<br/>note_count / author_count / interaction / collection]
    SQL --> SAMPLE[分层样本<br/>高互动 / 高收藏 / 高评论 / 高分享 / 最新]
    SQL --> KW[关键词 / 主题 / 周趋势 / 覆盖诊断]
    SQL --> CMT[评论样本]
    SQL --> COMP[竞品指标]

    FULL --> PACK[EvidencePack]
    SAMPLE --> PACK
    KW --> PACK
    CMT --> PACK
    COMP --> PACK

    PACK --> QUALITY[DataQuality<br/>ok / warning / limited]
    PACK --> LLM[多 Agent 分析]
    QUALITY --> LLM
    LLM --> FACT[FactCheckResult<br/>approved / downgraded / removed / disclaimers]
    FACT --> REPORT[可信报告输出]
```

这个设计可以在面试里强调一点：报告不是“大模型自由发挥”，而是“数据库证据包驱动的大模型分析”。因此，系统能解释数字来源，也能在数据不足时主动降级。

## 5. 模块职责

| 模块 | 主要职责 | 产品价值 |
| --- | --- | --- |
| XHS Data Center | 采集、回调、入库、搜索、看板、详情页 | 沉淀小红书数据资产 |
| DataScoutAgent | 从 PostgreSQL 生成 EvidencePack | 把底层数据变成报告可用证据 |
| LangGraph Workflow | 编排多 Agent 节点和 checkpoint | 让报告链路可追踪、可恢复 |
| JsonAgent / OfflineAgent | LLM JSON 输出或本地离线 fallback | 兼顾质量、稳定性和验证便利 |
| ReportDataComposer | 汇总分析结果为统一 JSON | 让报告能被前端和系统复用 |
| ExecutiveEditorAgent | 管理层摘要和主叙事 | 提升报告可读性和商业表达 |
| SectionWriterAgent | 生成章节化报告内容 | 让报告接近咨询交付物 |
| Renderers | 输出 Markdown 和 HTML | 覆盖内部文档和客户演示场景 |

## 6. 技术与产品取舍

**为什么不只做看板？**  
看板适合探索数据，但管理层和客户更需要明确结论。Agent 报告层把“用户自己看数据”变成“系统给出诊断和行动建议”。

**为什么需要多个 Agent？**  
品牌健康度报告包含指标、内容、受众、诊断、事实校验和表达。拆成多个 Agent 后，每个节点职责清晰，输出结构可验证，也便于后续替换模型或单独优化。

**为什么输出 JSON？**  
Markdown 和 HTML 解决阅读和展示，JSON 解决产品化复用。未来报告库、品牌页报告卡片、历史对比和行动追踪都可以基于 JSON 扩展。

**为什么保留 offline 模式？**  
offline 模式可以在不调用外部 LLM 的情况下验证取数、编排、schema、渲染和降级链路，适合测试、演示和异常排查。

## 7. 面试讲述建议

可以用这条主线介绍项目：

1. 我先做了小红书数据中台，解决数据采集、搜索、看板和详情页的数据资产沉淀问题。
2. 但真实业务里，品牌方不只需要查数据，还需要能拿去开会和提案的诊断报告。
3. 所以我在数据中台上设计了智能报告 Agent，把数据库里的笔记、评论、达人、关键词和竞品指标转成 EvidencePack。
4. 再通过多 Agent 分工，完成指标分析、内容洞察、受众洞察、诊断建议、事实校验和报告写作。
5. 最终输出 Markdown、HTML、JSON，分别服务文档协作、客户演示和系统复用。
6. 这个项目的关键不是“让 AI 写得更像报告”，而是“让 AI 基于可信数据和证据链生成可交付的业务结论”。

