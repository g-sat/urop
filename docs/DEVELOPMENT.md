# Development guide

## Setup

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Minimum `.env`:

```env
OPR_API_KEY=opr_live_your_key_here
DEFAULT_ANALYST_MODEL=llama3.1
```

Pull local models:

```powershell
ollama pull llama3.1
ollama pull phi3
```

## Run the API

From the repository root:

```powershell
python -m linkground
```

Or:

```powershell
uvicorn linkground.api.app:app --host 127.0.0.1 --port 8000
```

## Scripts

| Command | Purpose |
|---|---|
| `python scripts/build_dataset.py` | Write `data/evaluation_dataset.json` |
| `python scripts/run_benchmark.py` | Benchmark `/v1/evaluate` → `results/benchmark_metrics.csv` |
| `python scripts/generate_report.py` | Metrics report + plots under `results/` |
| `python scripts/evaluate_linked_answer.py ...` | Auto claim→link evaluation for arbitrary answers |

### Claim-linked evaluation example

```powershell
python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer.txt `
  --urls-file examples/url_pool.txt `
  --output examples/sample_linked_eval.json
```

## Conventions

- Keep service logic out of route handlers.
- Prefer clear names (`groundedness_score`, `trust_index`, `authority_multiplier`).
- Network failures in authority/crawl paths should degrade gracefully.
- Do not commit `.env`, `.cache/`, or `env/`.
- Generated files under `results/` are gitignored; keep the folder with `.gitkeep`.

## Project layout reminder

Active runtime: `linkground/` + `scripts/` + `examples/`  
Data: `data/evaluation_dataset.json`  
Docs: `docs/`
