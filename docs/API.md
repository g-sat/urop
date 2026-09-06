# API

`http://127.0.0.1:8000` · swagger at `/docs`

## GET /health

Version + status.

## GET /v1/trusted-domains

Domains discovery may use. Keep this list small and intentional.

## POST /v1/evaluate

Score a statement against URLs, or discover pages if `urls` is empty.

Legacy alias: `/v2/evaluate-provenance` (not shown in OpenAPI).

### Request

| Field | Required | Notes |
|---|---|---|
| `statement` | yes | alias: `llm_output_to_test` |
| `urls` | no | empty enables discovery |
| `model` | no | default `llama3.1` |
| `judge_runs` | no | 1–5 |
| `discover_evidence` | no | force discovery |
| `discovery_depth` | no | 0–2 |
| `max_discovered_urls` | no | 1–8 |

### Response

| Field | Notes |
|---|---|
| `groundedness_score` | support |
| `authority_multiplier` | OPR prestige |
| `trust_index` | support × prestige |
| `evidence` | per-URL source/origin |
| `evidence_mode` | caller / discovered / mixed |
| `discovery_weight` | 1.0 or discounted |
| `research` | see below |
| `notes` | short caveats |

### `research`

| Field | Notes |
|---|---|
| `support` / `prestige` | copies of the main scores |
| `prestige_inflation` | max(0, trust − support) |
| `citation_path` | caller vs discovery |
| `ethics_flags` | discovery / allowlist markers |
| `reporting_rule` | short reminder string |

### Status codes

`422` bad input / no evidence · `500` crawl or judge failure
