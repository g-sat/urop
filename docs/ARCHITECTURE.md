# Architecture (short)

Full developer narrative: **`docs/DEVELOPER_GUIDE.md`**.

Request path for `/v1/evaluate`:

```text
urls? → discovery (if needed)
     → Open PageRank (prestige)
     → crawl (live | cache | fallback)
     → judge LLM (SUPPORT / GROUNDEDNESS)  # LLM7 / Groq / Ollama via .env
     → apply evidence_quality × discovery_weight
     → attach research block

groundedness_score = primary (support)
trust_index        = groundedness × mean prestige (capped at 1)
```

## Packages

| Path | Role |
|---|---|
| `api/routes.py` | HTTP orchestration |
| `api/schemas.py` | models |
| `services/crawler.py` | fetch / cache / fallback |
| `services/authority.py` | OPR |
| `services/analyst.py` | closed-book judge |
| `services/discovery.py` | allowlisted URL finding |
| `services/trusted_sources.py` | domain allowlist |
| `services/weights.py` | discovery discount |
| `services/reporting.py` | research block |
| `services/scoring.py` | claim_count + parse judge output |
| `config.py` | env |

## Scripts

| Script | Role |
|---|---|
| `run_lcse_suite.py` | short LCSE suite |
| `evaluate_linked_answer.py` | split answer → URLs → score |
| `build_paper_dataset.py` | 50 long-answer paper cases |
| `run_benchmark.py` | paper benchmark → CSV |
| `generate_report.py` | MAE / swap Δ / ternary F1 + plots |

Crawl cache: `.cache/crawls/`. OPR cache: `.cache/opr_domain_ranks.json`.
