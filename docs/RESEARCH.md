# Research notes

Link-conditioned support estimation: score a claim against pages you can crawl, keep prestige separate, and run a few checks that catch common mixups.

## What we measure

1. Textual support (`groundedness_score`)
2. OPR prestige (`authority_multiplier`) — popularity, not truth
3. Whether the *cited* URL actually backs the claim (swaps)
4. When discovery / allowlist filled in for missing cites

`research.inflation = max(0, trust - support)`.  
`research.flags` / `research.source` tag discovery and discounts.

## Suite files

| File | What |
|---|---|
| `data/lcse/confound_grid.jsonl` | supported/unsupported × high/low prestige |
| `data/lcse/citation_swap.jsonl` | same claim, matched vs swapped URL |
| `data/lcse/ethics_audit.jsonl` | caller cites vs discovery |

Hard-zero support forces trust to zero, so prestige inflation only shows when support is partial. Prefer on-topic-but-wrong pages for the unsupported/high-prestige cells.

## Run

```powershell
python -m linkground
python scripts/run_lcse_suite.py
# --only confound|swaps|ethics
```

Writes `results/lcse_suite.json`.

## Scope

Not a world-truth oracle. Discovery misses niches outside the allowlist. The point is an auditable scoring protocol.
