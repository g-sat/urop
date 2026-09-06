# LinkGround

APIs for **measuring LLM outputs using linked web sources**.

Given an LLM statement and URLs, LinkGround:

1. Crawls the linked pages for evidence  
2. Scores **continuous groundedness** in `[0, 1]` with a local analyst model  
3. Looks up **Open PageRank** domain authority for those links  
4. Returns a **trust index** = groundedness × authority (capped at 1.0)

Novelty: link-conditioned measurement of LLM claims — not open-web memory fact-checking.

---

## Repository layout

```text
urop/
├── linkground/                 # API package
│   ├── api/                    # FastAPI app, routes, schemas
│   ├── services/               # authority, crawler, analyst, scoring, cache
│   ├── config.py
│   └── __main__.py             # python -m linkground
├── scripts/
│   ├── build_dataset.py        # Build data/evaluation_dataset.json
│   ├── run_benchmark.py        # Benchmark API on the dataset
│   ├── generate_report.py      # MAE/RMSE/F1 + plots
│   └── evaluate_linked_answer.py  # Auto claim→link evaluation
├── examples/                   # Sample answer, URL pool, sample output
├── data/                       # evaluation_dataset.json
├── results/                    # Benchmark outputs (gitignored contents)
├── docs/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick start

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# set OPR_API_KEY in .env

python -m linkground
```

Docs UI: http://127.0.0.1:8000/docs

### Example request

```powershell
curl -X POST http://127.0.0.1:8000/v1/evaluate `
  -H "Content-Type: application/json" `
  -d "{\"urls\":[\"https://en.wikipedia.org/wiki/Pluto\"],\"statement\":\"The IAU reclassified Pluto as a dwarf planet in 2006.\",\"model\":\"llama3.1\"}"
```

### Dataset, benchmark, report

```powershell
python scripts/build_dataset.py
python scripts/run_benchmark.py
python scripts/generate_report.py
```

### Auto claim → link evaluation

```powershell
python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer.txt `
  --urls-file examples/url_pool.txt
```

Add `--propose-urls` if the answer names sites without providing links.

---

## Response fields

| Field | Meaning |
|---|---|
| `groundedness_score` | Continuous support vs crawled evidence |
| `authority_multiplier` | Mean Open PageRank weight of the links |
| `trust_index` | Groundedness × authority (≤ 1.0) |
| `analyst_reasoning` | Claim / SUPPORT breakdown |
| `per_url_authority` | Per-link domain multipliers |
| `claim_count` | Atomic claims expected for scoring |

Request body uses `statement` (also accepts legacy `llm_output_to_test`).

Primary endpoint: `POST /v1/evaluate`  
Legacy alias (hidden): `POST /v2/evaluate-provenance`

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Development guide](docs/DEVELOPMENT.md)

---

## Requirements

- Python 3.10+
- Ollama (`llama3.1`, `phi3`, …)
- `OPR_API_KEY` (Open PageRank)
- Network access for crawling evidence URLs
