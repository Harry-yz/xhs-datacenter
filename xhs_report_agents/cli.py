from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from xhs_report_agents.agents import ReportPipeline
    from xhs_report_agents.config import get_settings
else:
    from .agents import ReportPipeline
    from .config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an XHS brand health report with multi-agent analysis.")
    parser.add_argument("--brand", required=True, help="目标品牌名")
    parser.add_argument("--category", required=True, help="品类/赛道，例如：高端护肤与美妆")
    parser.add_argument("--core-products", required=True, help="核心产品/产品线，逗号分隔")
    parser.add_argument("--competitor-brands", required=True, help="竞品品牌，逗号分隔，至少 1 个")
    parser.add_argument("--time-window", type=int, required=True, help="分析时间窗，单位天，例如 90")
    parser.add_argument("--max-notes", type=int, default=1000, help="最多纳入分析的笔记数")
    parser.add_argument("--max-comments", type=int, default=500, help="最多纳入分析的评论数")
    parser.add_argument("--output-dir", default=None, help="输出目录，默认 xhs_report_agents/outputs")
    parser.add_argument("--offline", action="store_true", help="不调用 DeepSeek，仅用本地 deterministic agents 验证数据和渲染链路")
    parser.add_argument("--enable-text-fallback", action="store_true", help="允许慢速全文 LIKE 补召回；默认关闭，避免大表超时")
    parser.add_argument("--checkpoint", choices=["memory", "sqlite", "none"], default="memory", help="LangGraph checkpoint 模式")
    parser.add_argument("--fast-model", default=None, help="分析节点使用的 DeepSeek 模型，默认 DEEPSEEK_FAST_MODEL")
    parser.add_argument("--pro-model", default=None, help="总编节点使用的 DeepSeek 模型，默认 DEEPSEEK_PRO_MODEL")
    parser.add_argument("--no-pro-editor", action="store_true", help="关闭 Pro 总编节点，使用确定性摘要降级")
    parser.add_argument("--no-external-context", action="store_true", help="关闭外部背景增强，仅使用数据库证据")
    parser.add_argument("--report-depth", choices=["sales-15"], default="sales-15", help="报告深度模板，默认企业售前 15 页")
    args = parser.parse_args(argv)
    core_products = _split_csv(args.core_products)
    competitor_brands = _split_csv(args.competitor_brands)
    if not core_products:
        parser.error("--core-products 至少需要 1 个核心产品")
    if not competitor_brands:
        parser.error("--competitor-brands 至少需要 1 个竞品品牌")
    if args.time_window <= 0:
        parser.error("--time-window 必须大于 0")

    settings = get_settings(args.output_dir, require_llm_key=not args.offline)
    settings = replace(
        settings,
        deepseek_fast_model=args.fast_model or settings.deepseek_fast_model,
        deepseek_pro_model=args.pro_model or settings.deepseek_pro_model,
    )
    pipeline = ReportPipeline(
        settings,
        offline=args.offline,
        checkpoint=args.checkpoint,
        use_pro_editor=not args.no_pro_editor,
        use_external_context=not args.no_external_context,
    )
    bundle = pipeline.generate(
        brand=args.brand.strip(),
        category=args.category.strip(),
        core_products=core_products,
        competitor_brands=competitor_brands,
        time_window=args.time_window,
        max_notes=args.max_notes,
        max_comments=args.max_comments,
        enable_text_fallback=args.enable_text_fallback,
        use_external_context=not args.no_external_context,
    )
    md_path, html_path = pipeline.write_outputs(bundle)
    print(f"markdown={md_path}")
    print(f"html={html_path}")
    if bundle.report_json:
        print(f"json={settings.output_dir / (html_path.stem + '.json')}")
        usage = bundle.report_json.get("model_usage", {}).get("executive_editor", {})
        if usage:
            print(f"executive_editor={usage.get('status')} model={usage.get('model')}")
        section_usage = bundle.report_json.get("model_usage", {}).get("section_writer", {})
        if section_usage:
            print(f"section_writer={section_usage.get('status')} model={section_usage.get('model')}")
        print(f"sections={len(bundle.report_json.get('report_sections', []))}")
    print(f"health_score={bundle.metric_analysis.overall_score:.1f}")
    print(f"data_quality={bundle.evidence_pack.data_quality.status}")
    if bundle.evidence_pack.data_quality.reasons:
        print("data_quality_reasons=" + ",".join(bundle.evidence_pack.data_quality.reasons))
    return 0


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
