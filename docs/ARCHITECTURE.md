# Architecture

## Problem

Large language models can produce fluent claims without grounding. LinkGround treats **URLs as the measurement instrument**: an LLM statement is scored only against evidence retrieved from the supplied links, then weighted by link-graph authority.

## Pipeline

```text
EvaluateRequest
   │
   ├─► Authority service ── Open PageRank (cached) ──► multipliers
   │
   ├─► Crawler service ──── page markdown (cached) ──► evidence block
   │
   └─► Analyst service ──── local Ollama chat ───────► SUPPORT scores
                                                      GROUNDEDNESS
                              │
                              ▼
                    trust_index = min(1, groundedness × mean_authority)
```

## Package map

| Module | Responsibility |
|---|---|
| `linkground.api.app` | FastAPI application factory |
| `linkground.api.routes` | `/health`, `/v2/evaluate-provenance` |
| `linkground.api.schemas` | Request/response contracts |
| `linkground.services.authority` | Domain authority via Open PageRank |
| `linkground.services.crawler` | Parallel crawl + evidence fallback |
| `linkground.services.analyst` | Prompting + local model call |
| `linkground.services.scoring` | Continuous score parsing |
| `linkground.services.cache` | Disk/memory caches |
| `linkground.config` | Environment-driven settings |

## Novelty points

1. **Link-conditioned measurement** — scoring is closed over crawled URL evidence, not open-web memory.
2. **Continuous groundedness (primary metric)** — the API stores real-valued SUPPORT / GROUNDEDNESS
   scores such as `0.768`, not only `{0, 1}`. MAE / RMSE / Pearson / Spearman use those raw floats,
   so `expected=1.0` vs `predicted=0.768` contributes error `0.232` instead of being collapsed to a
   binary hit/miss. Ternary labels (False / Partial / True) are a **secondary** view used only for
   classification reports and confusion matrices; they do not replace continuous evaluation.
3. **Authority fusion** — Open PageRank multiplies groundedness into a trust index.
4. **Multi-domain evaluation set** — interleaved true/false/partial cases across heterogeneous hosts.

## Continuous vs categorical evaluation

| Layer | What is stored / compared | Example |
|---|---|---|
| Primary (API + MAE/RMSE) | Continuous `groundedness_score ∈ [0,1]` | GT `1.00`, pred `0.77` → abs error `0.23` |
| Secondary (F1 / confusion) | Binned class for reporting only | `0.77` → class `True` if `> 0.75` |

Do **not** judge model quality from F1 alone. Prefer MAE, RMSE, and rank correlation when arguing
that LinkGround measures graded support against links.


## Caching

- `.cache/opr_domain_ranks.json` — domain → authority multiplier
- `.cache/crawls/<sha1>.txt` — crawled page text

Caches make repeated benchmark URLs much faster after the first pass.
