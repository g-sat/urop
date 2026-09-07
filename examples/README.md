# Examples

| File | Role |
|---|---|
| `sample_answer.txt` | EG1 — Three.js answer |
| `url_pool.txt` | EG1 URL pool |
| `sample_answer_historic.txt` | EG2 — historic sites answer |
| `url_pool_historic.txt` | EG2 URL pool |

```powershell
python -m linkground

python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer.txt `
  --urls-file examples/url_pool.txt `
  --output results/eg1_claims.json

python scripts/rescore_linked_eval.py `
  --from-json results/eg1_claims.json `
  --output results/eg1_llm7.json `
  --model mistral-Nemo-Instruct-2407 --sleep 2
```

Suite data is under `data/lcse/`. Canonical scores: `results/COMPARISON.md`.
