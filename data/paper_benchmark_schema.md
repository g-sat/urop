# Paper benchmark dataset

Built by `scripts/build_paper_dataset.py` → `data/paper_benchmark.jsonl`.

Longer multi-sentence answers with controlled conditions for LCSE experiments.

**Constraint:** `statement` never embeds URLs. Attribution is only via `urls[]`. Supported and swapped pairs share identical statement text.

## Fields

| Field | Meaning |
|---|---|
| `id` | stable case id |
| `topic` | topic family |
| `condition` | `supported` / `swapped` / `unsupported` / `soft_wrong` / `mixed` |
| `pair_id` | shared id for supported↔swapped attribution pairs |
| `statement` | long answer text (**no** inline URLs) |
| `urls` | evidence URLs sent to `/v1/evaluate` |
| `label_support` | human target support in [0, 1] |
| `prestige_bin` | `high` / `low` |
| `claim_count` | optional; forced `2` for `mixed` |
| `notes` | short rationale |
| `answer_chars` | length of statement |

## Conditions

| Condition | Intent |
|---|---|
| `supported` | true long answer + matching URL |
| `swapped` | **identical** statement to supported + unrelated URL |
| `unsupported` | blatantly false long answer + on-topic URL |
| `soft_wrong` | related but wrong claim on prestige page (mid label) |
| `mixed` | true half + false half; API `claim_count=2`, mean SUPPORT |

## Primary metrics (not overall F1)

- MAE by condition
- Citation-swap Δ = groundedness(supported) − groundedness(swapped)

## Run

```powershell
python scripts/build_paper_dataset.py
python -m linkground
python scripts/run_benchmark.py --sleep 2
python scripts/generate_report.py
```
