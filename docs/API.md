# API reference

Base URL (local): `http://127.0.0.1:8000`  
OpenAPI UI: `/docs`

## `GET /health`

```json
{
  "status": "ok",
  "service": "linkground",
  "version": "2.2.0",
  "cache_dir": ".../.cache"
}
```

## `POST /v1/evaluate`

Measure an LLM statement against linked sources.

Legacy alias (still accepted, not shown in schema): `POST /v2/evaluate-provenance`

### Request

| Field | Type | Required | Description |
|---|---|---|---|
| `urls` | `string[]` | yes | Evidence links |
| `statement` | `string` | yes | Statement to measure (also accepts `llm_output_to_test`) |
| `model` | `string` | no | Ollama analyst model (default `llama3.1`) |

```json
{
  "urls": [
    "https://en.wikipedia.org/wiki/Bitcoin",
    "https://bitcoin.org/bitcoin.pdf"
  ],
  "statement": "Satoshi Nakamoto authored the Bitcoin whitepaper.",
  "model": "llama3.1"
}
```

### Response

| Field | Type | Description |
|---|---|---|
| `groundedness_score` | `number` | Continuous support in `[0, 1]` |
| `authority_multiplier` | `number` | Mean Open PageRank multiplier |
| `trust_index` | `number` | Groundedness × authority (≤ 1) |
| `analyst_reasoning` | `string` | Analyst SUPPORT breakdown |
| `per_url_authority` | `object[]` | Per-link domain multipliers |
| `model_used` | `string` | Analyst model name |
| `claim_count` | `integer` | Atomic claims expected for scoring |

### Status codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 422 | Validation error |
| 500 | Crawl / analyst / pipeline failure |
