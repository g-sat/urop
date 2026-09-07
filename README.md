# LinkGround

Scores an LLM statement against linked pages.

Support (`groundedness_score`) and prestige (`authority_multiplier`, Open PageRank) stay separate on purpose. `trust_index` = support × prestige is secondary.

Version `3.0.0`.

## Layout

```text
linkground/          FastAPI + services
data/lcse/           suite JSONL (swaps, confound, ethics)
scripts/             suite / linked-eval / rescore / benchmark
examples/            EG1 + EG2 answers and URL pools
docs/                research + API notes
results/             canonical outputs (see COMPARISON.md)
```

## Setup

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set in `.env`:
- `OPR_API_KEY`
- LLM7 judge (recommended):

```env
JUDGE_BASE_URL=https://api.llm7.io/v1
JUDGE_API_KEY=...
DEFAULT_ANALYST_MODEL=mistral-Nemo-Instruct-2407
```

```powershell
python -m linkground
```

http://127.0.0.1:8000/docs

## Quick evaluate

```powershell
curl -X POST http://127.0.0.1:8000/v1/evaluate `
  -H "Content-Type: application/json" `
  -d "{\"urls\":[\"https://en.wikipedia.org/wiki/Pluto\"],\"statement\":\"The IAU reclassified Pluto as a dwarf planet in 2006.\",\"model\":\"mistral-Nemo-Instruct-2407\"}"
```

## Experiments

```powershell
# Paper suite
python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
python scripts/run_lcse_suite.py --only confound --output results/lcse_confound.json

# Long answers (EG1 / EG2)
python scripts/evaluate_linked_answer.py --answer-file examples/sample_answer.txt --urls-file examples/url_pool.txt --output results/eg1_claims.json
python scripts/rescore_linked_eval.py --from-json results/eg1_claims.json --output results/eg1_llm7.json --model mistral-Nemo-Instruct-2407 --sleep 2
```

## Docs

`docs/RESEARCH.md` · `docs/PAPER_ROADMAP.md` · `docs/ARCHITECTURE.md` · `docs/API.md` · `docs/LIMITATIONS.md` · `docs/DEVELOPMENT.md` · `results/COMPARISON.md`

## Deps

Python 3.10+, network, `OPR_API_KEY`, LLM7 (or Ollama / Groq via `.env`).
