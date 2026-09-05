# Development guide

## Setup

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set at least:

```env
OPR_API_KEY=opr_live_your_key_here
DEFAULT_ANALYST_MODEL=llama3.1
```

Ensure Ollama is running and the chosen model is pulled:

```powershell
ollama pull llama3.1
ollama pull phi3
```

## Run the API

From the repository root (so `linkground` is importable):

```powershell
python -m linkground
```

Or with uvicorn directly:

```powershell
uvicorn linkground.api.app:app --host 127.0.0.1 --port 8000
```

## Scripts

| Script | Purpose |
|---|---|
| `scripts/build_dataset.py` | Build `data/evaluation_dataset.json` |
| `scripts/run_benchmark.py` | Call the API on N cases × models |
| `scripts/generate_report.py` | MAE/RMSE/F1 + plots under `results/` |

## Coding conventions

- Prefer clear names (`groundedness_score`, `authority_multiplier`) over slang.
- Keep service logic out of route handlers.
- Network failures in authority/crawl paths should degrade gracefully, not crash the API.
- Do not commit `.env`, `.cache/`, or `env/`.

## Legacy code

Older prototypes live under `archive/` (`src/`, `builders/`, `test_env/`).  
They are kept for reference only and are not part of the runtime path.
