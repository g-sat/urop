# Examples

Sample answers I use to smoke-test linked evaluation.

```powershell
python -m linkground

python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer.txt `
  --urls-file examples/url_pool.txt

python scripts/evaluate_linked_answer.py `
  --answer-file examples/sample_answer_historic.txt `
  --urls-file examples/url_pool_historic.txt
```

| File | What |
|---|---|
| `sample_answer.txt` | Three.js answer |
| `url_pool.txt` | its URL pool |
| `sample_answer_historic.txt` | historic-sites answer |
| `url_pool_historic.txt` | its URL pool |

Research suite data is under `data/lcse/`, not here.
