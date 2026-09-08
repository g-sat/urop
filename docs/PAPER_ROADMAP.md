# Paper roadmap (LCSE)

Methods-style research track. Not a product pitch.

## Claim

Evaluating LLM answers “with sources” often mixes textual support with web prestige; **LCSE** keeps those signals separate and tests whether the *cited* page actually supports the claim.

## Lead result

| Experiment | Result | File |
|---|---|---|
| Citation swaps | mean Δ ≈ **0.87** | `results/lcse_swaps.json` |
| Confound grid | soft-wrong expanded; UH often hard-zero | `results/lcse_confound.json` |
| EG1 / EG2 | case studies only (LLM7) | `results/eg1_llm7.json`, `results/eg2_llm7.json` |

**Lead with citation attribution, not long-answer means.**

## Frozen stack

- Judge (case studies): LLM7 `mistral-Nemo-Instruct-2407`
- Suite tables on disk: Groq `openai/gpt-oss-20b` run (re-run on LLM7 when ready)
- Split: local `llama3.1`
- Primary metric: `groundedness_score`

## Still needed

1. Fix weak swap pairs (e.g. B-009 matched=0)
2. Soft-wrong UH mid-scale scores (0.2–0.5) for inflation
3. Run `scripts/run_benchmark.py` on `data/paper_benchmark.jsonl` and report **MAE by condition + swap Δ** (not overall F1)
4. Related-work + ethics (allowlist bias) sections

## Writing order

1. Problem (fused trust)
2. Method (LCSE)
3. Exp B swaps
4. Exp A confound + limits
5. Paper benchmark (MAE + swap Δ on long answers)
6. Exp C discovery disclosure
7. Appendix: EG1/EG2
8. Limitations

## Commands

```powershell
python -m linkground
python scripts/build_paper_dataset.py
python scripts/run_benchmark.py --sleep 2
python scripts/generate_report.py
python scripts/run_lcse_suite.py --only swaps --output results/lcse_swaps.json
```

Details: `results/COMPARISON.md` · `docs/RESEARCH.md` · `data/paper_benchmark_schema.md`
