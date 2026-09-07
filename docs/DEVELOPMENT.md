# Development

## Setup

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` sections (see `.env.example`):

1. **API server** — `API_HOST`, `API_PORT`  
2. **Open PageRank** — `OPR_API_KEY`  
3. **Judge** — `JUDGE_BASE_URL`, `JUDGE_API_KEY`, `DEFAULT_ANALYST_MODEL`  
4. **Ollama** — split / offline (`LOCAL_SPLIT_MODEL`)  
5. **Tuning** — evidence budget, discovery, cache  

```env
OPR_API_KEY=...
JUDGE_BASE_URL=https://api.llm7.io/v1
JUDGE_API_KEY=...
DEFAULT_ANALYST_MODEL=mistral-Nemo-Instruct-2407
```

## API

```powershell
python -m linkground
```

If port 8000 is stuck:

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select OwningProcess
Stop-Process -Id <pid> -Force
```

## Common commands

```powershell
python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
python scripts/rescore_linked_eval.py --from-json results/eg1_claims.json --output results/eg1_llm7.json --model mistral-Nemo-Instruct-2407 --sleep 2
python scripts/run_benchmark.py
python scripts/generate_report.py
```

## Conventions

- Business logic lives in `services/`, not route handlers.
- Support stays the primary field name (`groundedness_score`).
- Don’t add silent prestige into the primary score.
- Results go under `results/`; datasets under `data/` / `data/lcse/`.
