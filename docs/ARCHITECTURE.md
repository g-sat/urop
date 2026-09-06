# Architecture

Request path for `/v1/evaluate`:

```text
urls? → discovery (if needed)
     → Open PageRank (prestige)
     → crawl (live | cache | fallback)
     → Ollama judge (SUPPORT / GROUNDEDNESS)
     → apply evidence_quality × discovery_weight
     → attach research block

groundedness_score = primary
trust_index        = groundedness × mean prestige (capped at 1)
```

## Packages

| Path | Role |
|---|---|
| `api/routes.py` | HTTP |
| `api/schemas.py` | models |
| `services/crawler.py` | fetch / cache / fallback |
| `services/authority.py` | OPR |
| `services/analyst.py` | judge |
| `services/discovery.py` | URL finding |
| `services/trusted_sources.py` | allowlist |
| `services/weights.py` | discovery discount |
| `services/reporting.py` | research block |
| `services/scoring.py` | parse judge output |
| `config.py` | env |

## Scripts

| Script | Role |
|---|---|
| `run_lcse_suite.py` | suite runner |
| `evaluate_linked_answer.py` | split answer → URLs → score |
| `run_benchmark.py` | older dataset loop |
| `generate_report.py` | MAE/RMSE plots |

Crawl cache: `.cache/crawls/`. OPR cache: `.cache/opr_domain_ranks.json`.
