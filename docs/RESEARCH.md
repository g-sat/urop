# Research notes (LCSE)

LCSE = link-conditioned support estimation.

When people score LLM answers “with sources,” they often fold PageRank or a trusted-site list into the same number as textual support. This project keeps those apart and ships a small suite that tries to break the mixups.

## Setup

1. Score against retrieved page text (`groundedness_score`).
2. Report OPR prestige separately (`authority_multiplier`).
3. Run citation swaps.
4. Flag discovery / allowlist use.

## Spine A — prestige confound

Cells: supported/unsupported × high/low prestige.

Compare `trust_index` to `groundedness_score`.  
`research.prestige_inflation = max(0, trust - support)`.

Note: support `0` forces trust `0`, so UH cases that are total contradictions will not show inflation. Prefer pages that are on-topic but do not actually support the claim.

Data: `data/lcse/confound_grid.jsonl`

## Spine B — citation attribution

Paired rows: same statement, correct URL vs wrong URL.  
`delta_swap = matched_support - swapped_support` should be clearly positive.

Data: `data/lcse/citation_swap.jsonl`

## Spine C — allowlist / discovery

Same statement with caller URLs vs discovery.  
Check `research.ethics_flags` and that writeups still lead with support.

Data: `data/lcse/ethics_audit.jsonl`

## Run

```powershell
python -m linkground
python scripts/run_lcse_suite.py --spine all
```

Writes `results/lcse_suite.json`.

## Scope

Not a world-truth oracle. Not “OPR means reliable.” Discovery will miss niches outside the allowlist. The point is a scoring protocol you can audit.
