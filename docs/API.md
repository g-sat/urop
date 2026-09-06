# API

`http://127.0.0.1:8000` · `/docs`

## GET /health

## GET /v1/trusted-domains

## POST /v1/evaluate

| request | notes |
|---|---|
| `statement` | required |
| `urls` | optional; empty → discovery |
| `model` | default llama3.1 |
| `judge_runs` | 1–5 |
| `discover_evidence` | bool |
| `discovery_depth` | 0–2 |
| `max_discovered_urls` | 1–8 |

| response | notes |
|---|---|
| `groundedness_score` | support |
| `authority_multiplier` | OPR |
| `trust_index` | support × OPR |
| `evidence` / `evidence_mode` / `discovery_weight` | provenance |
| `research.support` / `prestige` / `inflation` | extras |
| `research.source` | cited / discovered / mixed / none |
| `research.flags` | short tags |

`422` no evidence · `500` pipeline error
