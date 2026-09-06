# LCSE data

JSONL under `data/lcse/`. One object per line.

## Shared fields

| Field | Required | Notes |
|---|---|---|
| `id` | yes | stable id |
| `spine` | yes | `A` confound / `B` swaps / `C` ethics (dataset tag) |
| `statement` | yes | claim text |
| `urls` | yes | may be `[]` for discovery |
| `label_support` | no | human label in [0,1] when you have it |

## `confound_grid.jsonl`
`cell`: `SH` | `SL` | `UH` | `UL`  
`prestige_bin`, `support_bin`

## `citation_swap.jsonl`
`pair_id`, `condition`: `matched` | `swapped` | `missing`

## `ethics_audit.jsonl`
`regime`: `caller` | `discovery` | `mixed`  
`bias_risk`: short tag
