# Architecture

## Problem

LLMs can produce fluent claims without grounding. LinkGround treats **URLs as the measurement instrument**: a statement is scored only against evidence retrieved from the supplied links, then weighted by link-graph authority.

## Pipeline

```text
EvaluateRequest
   │
   ├─► authority service ── Open PageRank (cached) ──► multipliers
   │
   ├─► crawler service ──── page markdown (cached) ──► evidence block
   │
   └─► analyst service ──── local Ollama chat ───────► SUPPORT scores
                                                      GROUNDEDNESS
                              │
                              ▼
                    trust_index = min(1, groundedness × mean_authority)
```

## Package map

| Module | Responsibility |
|---|---|
| `linkground.api.app` | FastAPI application factory |
| `linkground.api.routes` | `/health`, `/v1/evaluate` |
| `linkground.api.schemas` | Request / response contracts |
| `linkground.services.authority` | Domain authority via Open PageRank |
| `linkground.services.crawler` | Parallel crawl + evidence fallback |
| `linkground.services.analyst` | Prompting + local model call |
| `linkground.services.scoring` | Continuous score parsing |
| `linkground.services.cache` | Disk / memory caches |
| `linkground.services.evidence` | Topic fallbacks when crawls are empty |
| `linkground.config` | Environment-driven settings |

## Scripts

| Script | Role |
|---|---|
| `scripts/build_dataset.py` | Build `data/evaluation_dataset.json` |
| `scripts/run_benchmark.py` | Call `/v1/evaluate` on N cases × models |
| `scripts/generate_report.py` | Continuous + categorical metrics and plots |
| `scripts/evaluate_linked_answer.py` | Split answer → assign URLs → score → aggregate |

## Novelty

1. **Link-conditioned measurement** — closed over crawled URL evidence, not model memory.
2. **Continuous groundedness (primary)** — real-valued SUPPORT / GROUNDEDNESS (e.g. `0.77`). MAE / RMSE / correlation use raw floats; ternary bins are secondary for classification views only.
3. **Authority fusion** — Open PageRank multiplies groundedness into `trust_index`.
4. **Claim→link routing** — long answers can be auto-split and each claim scored against its matched URL(s).

## Continuous vs categorical evaluation

| Layer | Compared values | Example |
|---|---|---|
| Primary (API + MAE/RMSE) | Continuous `groundedness_score ∈ [0,1]` | GT `1.00`, pred `0.77` → abs error `0.23` |
| Secondary (F1 / confusion) | Binned class for reporting only | `0.77` → class `True` if `> 0.75` |

## Caching

- `.cache/opr_domain_ranks.json` — domain → authority multiplier  
- `.cache/crawls/<sha1>.txt` — crawled page text  
