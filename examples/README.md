# LinkGround examples

Sample inputs for the claim-linked evaluator:

```powershell
python -m linkground

python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer.txt `
  --urls-file examples/url_pool.txt `
  --output examples/sample_linked_eval.json
```

| File | Purpose |
|---|---|
| `sample_answer.txt` | Example LLM answer to evaluate |
| `url_pool.txt` | Evidence URLs for claim assignment |
| `sample_linked_eval.json` | Example aggregated evaluation output |
