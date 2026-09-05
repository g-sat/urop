# LinkGround

APIs for **measuring LLM outputs using linked web sources**.

Given an LLM statement and a set of URLs, LinkGround:

1. Crawls the linked pages for evidence  
2. Scores **continuous groundedness** in \\([0, 1]\\) with a local analyst model  
3. Looks up **Open PageRank** domain authority for those links  
4. Returns a **trust index** = groundedness × authority (capped at 1.0)

This is the core novelty: link-conditioned measurement of LLM claims, not free-form fact checking from model memory.

---

## Repository layout

```text
urop/
├── linkground/                 # Installable API package
│   ├── api/                    # FastAPI app, routes, schemas
│   ├── services/               # Authority, crawl, analyst, scoring, cache
│   ├── config.py
│   └── __main__.py             # python -m linkground
├── scripts/                    # Developer CLI utilities
│   ├── build_dataset.py
│   ├── run_benchmark.py
│   └── generate_report.py
├── data/                       # Evaluation datasets
├── results/                    # Benchmark metrics and plots
├── docs/                       # Architecture and API docs
├── archive/                    # Legacy prototypes (not used at runtime)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick start

### 1. Environment

```powershell
cd C:\Users\sathw\Desktop\urop
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set OPR_API_KEY
```

### 2. Start the API

```powershell
python -m linkground
```

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. Example request

```powershell
curl -X POST http://127.0.0.1:8000/v2/evaluate-provenance `
  -H "Content-Type: application/json" `
  -d "{\"urls\":[\"https://en.wikipedia.org/wiki/Pluto\"],\"llm_output_to_test\":\"The IAU reclassified Pluto as a dwarf planet in 2006.\",\"model\":\"llama3.1\"}"
```

### 4. Dataset, benchmark, report

```powershell
python scripts/build_dataset.py
python scripts/run_benchmark.py
python scripts/generate_report.py
```

Outputs land in `results/`.

---

## Response fields

| Field | Meaning |
|---|---|
| `groundedness_score` | Continuous support vs crawled link evidence |
| `source_authority_multiplier` | Mean Open PageRank weight of the links |
| `final_verified_trust_index` | Groundedness × authority (≤ 1.0) |
| `academic_reasoning` | Analyst claim / SUPPORT breakdown |
| `per_url_authority` | Per-link domain multipliers |

Backward-compatible request alias: `llm_output_to_test` (same as `statement`).

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Development guide](docs/DEVELOPMENT.md)

---

## Requirements

- Python 3.10+
- Ollama with models such as `llama3.1` / `phi3`
- Open PageRank API key (`OPR_API_KEY`)
- Network access for crawling evidence URLs
