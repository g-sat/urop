# Development

Full architecture and design rationale: **`docs/DEVELOPER_GUIDE.md`**.

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
python scripts/build_paper_dataset.py
python scripts/run_benchmark.py --sleep 2
python scripts/generate_report.py
python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
```

## Conventions

- Business logic lives in `services/`, not route handlers.
- Support stays the primary field name (`groundedness_score`).
- Don’t add silent prestige into the primary score.
- Results go under `results/`; datasets under `data/` / `data/lcse/`.
