# XHS Report Agents

Standalone multi-agent brand health report generator for the existing Xiaohongshu database.

```bash
python /opt/xhs_data_center/xhs_report_agents/cli.py \
  --brand "品牌名" \
  --aliases "别名1,别名2" \
  --competitors "竞品1,竞品2" \
  --days 90
```

Environment:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`, default `https://api.deepseek.com`
- `DEEPSEEK_MODEL`, default `deepseek-v4-flash`
- `DEEPSEEK_FAST_MODEL`, default `DEEPSEEK_MODEL` or `deepseek-v4-flash`
- `DEEPSEEK_PRO_MODEL`, default `deepseek-v4-pro`
- `DATABASE_URL` or `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD`

Outputs are written only to `xhs_report_agents/outputs/` unless `--output-dir` is provided. Each run writes Markdown, premium single-file HTML, and structured JSON.

By default the data scout uses indexed sources (`xhs_note_term_rel`, `xhs_note_brand_rel`, and `search_keyword`) and avoids slow full-table text scans. Core metrics are full relevant-database aggregations. `--max-notes` only controls the evidence sample sent to LLM agents. Use `--enable-text-fallback` only for small brands or maintenance runs where a slower legacy text fallback is acceptable.

Model routing:

- Flash model: metric, content, audience, diagnosis, fact-check, and Markdown writer agents.
- Pro model: `ExecutiveEditorAgent` only, for final title, executive summary, key findings, and management diagnosis.
- `--no-pro-editor`: disable Pro editor and use deterministic summary fallback.
- `--fast-model` / `--pro-model`: override model names per run.

The orchestrator is a LangGraph `StateGraph`. Install the isolated dependency before running:

```bash
/opt/xhs_data_center/.venv/bin/pip install -r /opt/xhs_data_center/xhs_report_agents/requirements.txt
```

Checkpoint modes:

- `--checkpoint memory`: default in-process checkpoint.
- `--checkpoint sqlite`: persistent checkpoint when the installed LangGraph package provides SQLite saver.
- `--checkpoint none`: no checkpoint.

For local verification without sending database evidence to an external LLM:

```bash
python /opt/xhs_data_center/xhs_report_agents/cli.py --brand "品牌名" --offline
```
