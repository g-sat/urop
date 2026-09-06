# Development

## Setup

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` at minimum:

```env
OPR_API_KEY=...
DEFAULT_ANALYST_MODEL=llama3.1
```

```powershell
ollama pull llama3.1
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
python scripts/run_lcse_suite.py --spine all
python scripts/evaluate_linked_answer.py --answer-file examples/sample_answer.txt --urls-file examples/url_pool.txt
python scripts/run_benchmark.py
python scripts/generate_report.py
```

## Conventions

- Business logic lives in `services/`, not route handlers.
- Support stays the primary field name (`groundedness_score`).
- Don’t add silent prestige into the primary score.
- Results go under `results/`; datasets under `data/` / `data/lcse/`.
