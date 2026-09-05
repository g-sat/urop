# API reference

Base URL (local): `http://127.0.0.1:8000`  
OpenAPI UI: `/docs`

## `GET /health`

Liveness check.

```json
{
  "status": "ok",
  "service": "linkground",
  "version": "2.1.0",
  "cache_dir": ".../.cache"
}
```

## `POST /v2/evaluate-provenance`

Measure an LLM statement against linked sources.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `urls` | `string[]` | yes | Evidence links |
| `llm_output_to_test` | `string` | yes | Statement to measure (alias: `statement`) |
| `model` | `string` | no | Ollama analyst model (default `llama3.1`) |

Example:

```json
{
  "urls": [
    "https://en.wikipedia.org/wiki/Bitcoin",
    "https://bitcoin.org/bitcoin.pdf"
  ],
  "llm_output_to_test": "Satoshi Nakamoto authored the Bitcoin whitepaper.",
  "model": "llama3.1"
}
```

### Response body

| Field | Type | Description |
|---|---|---|
| `groundedness_score` | `number` | Continuous support in `[0, 1]` |
| `source_authority_multiplier` | `number` | Mean Open PageRank multiplier |
| `final_verified_trust_index` | `number` | Groundedness × authority (≤ 1) |
| `academic_reasoning` | `string` | Analyst breakdown |
| `per_url_authority` | `object[]` | Per-link domain multipliers |
| `model_used` | `string` | Analyst model name |
| `claim_count_expected` | `integer` | 1 for atomic, 2 for mixed claims |

### Status codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 422 | Validation error |
| 500 | Crawl/analyst/pipeline failure |
