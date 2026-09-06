# Limitations

LinkGround scores a claim against pages it can crawl. It does not decide whether something is true in the world.

Known issues:

**`trust_index`.** This is support times Open PageRank. PageRank is popularity. A well-linked page that only weakly matches the claim can still look strong if you only glance at `trust_index`. Prefer `groundedness_score`. The `research.prestige_inflation` field is there so the gap is visible.

**Hard zeros hide the confound.** If the judge returns support `0`, trust is also `0`, so high prestige never shows up as inflation. For Spine A you need “related but wrong” pages that land in the middle of the scale, not only blatant contradictions.

**Discovery.** Empty `urls` triggers Wikipedia / allowlist search. That helps coverage. It also biases toward English reference sites. Discovered evidence is scaled by `DISCOVERY_SCORE_FACTOR` (default `0.55`). Treat discovery as a fallback path, not a replacement for real citations.

**Allowlist.** `GET /v1/trusted-domains` is an engineering constraint, not an epistemology. Whatever is missing from that list is invisible to discovery.

**Judge.** Scoring goes through a local Ollama model. Expect format retries, run-to-run jitter, and a pile of scores near `0.9`. `judge_runs` averages a few passes; it does not remove the bias.

**Crawls.** Heavy JS, PDFs, and paywalls often come back thin. We fall back to short seed text, mark it as `fallback`, and cut `evidence_quality`. Those fallbacks are not written into the live crawl cache.

**Claim → URL routing.** The linked-answer script matches claims to a URL pool with overlap + a few topic hints. That fixed the UNESCO→engagingplaces mistake we hit in testing. It will break on new domains until someone updates the hints or replaces it with a trained aligner.

**Reporting.** Use MAE / RMSE / correlation on continuous support. The ternary F1 path in `generate_report.py` is leftover convenience, not the main result.
