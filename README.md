# LinkGround

API for scoring an LLM statement against linked pages.

Support (`groundedness_score`) and prestige (`authority_multiplier`, from Open PageRank) are separate on purpose. Mixing them into one “trust” number is how a popular wrong page starts looking reliable. `trust_index` still exists as support × prestige, but it is not the primary metric.

## Outputs

| Field | Meaning |
|---|---|
| `groundedness_score` | support vs crawled evidence |
| `authority_multiplier` | mean OPR prestige |
| `trust_index` | support × prestige |
| `discovery_weight` | `< 1` when evidence was auto-found |
| `research.support` / `prestige` | copies of the main scores |
| `research.inflation` | max(0, trust − support) |
| `research.source` | cited / discovered / mixed |
| `research.flags` | discovery / discount tags |

Version `3.0.0`.

## Layout

```text
linkground/     FastAPI + services
data/lcse/      eval suite JSONL
scripts/        suite, linked-eval, benchmark
examples/       sample answers + URL pools
docs/
results/
```

## Run

```powershell
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# set OPR_API_KEY

python -m linkground
```

http://127.0.0.1:8000/docs

```powershell
curl -X POST http://127.0.0.1:8000/v1/evaluate `
  -H "Content-Type: application/json" `
  -d "{\"urls\":[\"https://en.wikipedia.org/wiki/Pluto\"],\"statement\":\"The IAU reclassified Pluto as a dwarf planet in 2006.\",\"model\":\"llama3.1\"}"
```

```powershell
curl -X POST http://127.0.0.1:8000/v1/evaluate `
  -H "Content-Type: application/json" `
  -d "{\"statement\":\"The Colosseum in Rome is an ancient amphitheatre.\",\"discover_evidence\":true,\"model\":\"llama3.1\"}"
```

## Experiments

```powershell
python scripts/run_lcse_suite.py
# optional: --only confound|swaps|ethics
```

Suite files live in `data/lcse/`. Notes in `docs/RESEARCH.md`.

## Long answers

```powershell
python scripts/evaluate_linked_answer.py --answer-file examples/sample_answer.txt --urls-file examples/url_pool.txt
python scripts/evaluate_linked_answer.py --answer-file examples/sample_answer_historic.txt --urls-file examples/url_pool_historic.txt
```

## Docs

`docs/RESEARCH.md` · `docs/ARCHITECTURE.md` · `docs/API.md` · `docs/LIMITATIONS.md` · `docs/DEVELOPMENT.md`

## Deps

Python 3.10+, Ollama, `OPR_API_KEY`, network.
