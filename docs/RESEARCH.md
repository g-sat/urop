# Research notes

Link-conditioned support estimation: score a claim against crawled pages, keep prestige separate, run checks that catch common mixups.

## Signals

1. Textual support — `groundedness_score`
2. OPR prestige — `authority_multiplier` (popularity, not truth)
3. Citation swaps — matched vs wrong URL
4. Discovery / allowlist — when cites are missing

`research.inflation = max(0, trust - support)`.

## Suite (`data/lcse/`)

| File | Role |
|---|---|
| `citation_swap.jsonl` | matched vs swapped URL |
| `confound_grid.jsonl` | support × prestige cells |
| `ethics_audit.jsonl` | caller vs discovery |

Lead result: citation swaps. Soft-wrong UH cells are needed before prestige inflation shows cleanly (hard-zero support forces trust 0).

## Run

```powershell
python -m linkground
python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
python scripts/run_lcse_suite.py --only confound --output results/lcse_confound.json
```

Canonical numbers: `results/COMPARISON.md` · roadmap: `docs/PAPER_ROADMAP.md`.
