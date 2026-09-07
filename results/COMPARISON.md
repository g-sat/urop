# Current results (canonical)

Judge for EG case studies: LLM7 `mistral-Nemo-Instruct-2407`  
Suite swaps/confound tables: Groq `openai/gpt-oss-20b` (frozen run)

## Files

| File | What |
|---|---|
| `eg1_claims.json` | EG1 claim split (Three.js) |
| `eg1_llm7.json` | EG1 scored with LLM7 |
| `eg2_claims.json` | EG2 claim split (historic) |
| `eg2_llm7.json` | EG2 scored with LLM7 |
| `lcse_swaps.json` | citation-swap suite |
| `lcse_confound.json` | prestige confound suite |

## EG case studies

| Example | Claims | Mean g | Mean t | Mean claim latency | Wall |
|---|---:|---:|---:|---:|---:|
| EG1 Three.js | 14 | 0.756 | 0.791 | 4.6s | 93s |
| EG2 Historic | 25 | 0.792 | 0.853 | 4.8s | 169s |

## Suite (paper lead)

| Suite | Headline |
|---|---|
| Citation swaps | mean Δ(matched − swapped) ≈ **0.868** |
| Confound | SH high; UH still often hard-zero (known limit) |

## Re-run

```powershell
python -m linkground

python scripts/rescore_linked_eval.py `
  --from-json results/eg1_claims.json `
  --output results/eg1_llm7.json `
  --model mistral-Nemo-Instruct-2407 --sleep 2

python scripts/rescore_linked_eval.py `
  --from-json results/eg2_claims.json `
  --output results/eg2_llm7.json `
  --model mistral-Nemo-Instruct-2407 --sleep 2

python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
python scripts/run_lcse_suite.py --only confound --output results/lcse_confound.json
```
