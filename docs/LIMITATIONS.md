# Limitations

LinkGround scores a claim against pages it can crawl. It does not decide whether something is true in the world.

**`trust_index`.** Support × Open PageRank. PageRank is popularity. Prefer `groundedness_score`. `research.inflation` shows the gap when trust outruns support.

**Hard zeros.** Support `0` forces trust `0`, so high prestige never shows as inflation. For confound cells you need on-topic-but-wrong pages that land mid-scale, not only total contradictions.

**Discovery.** Empty `urls` triggers Wikipedia / allowlist search. Biases toward English reference sites. Scaled by `DISCOVERY_SCORE_FACTOR` (default `0.55`). Fallback path, not a substitute for real cites. Linked-answer eval only forces discovery when there is no usable URL assignment; weak matches can use hybrid (caller + discovery). If every caller crawl is `fallback`, the API may mix in discovery automatically.

**Allowlist.** `GET /v1/trusted-domains` is an engineering constraint. Missing domains are invisible to discovery.

**Judge.** Local Ollama. Format retries, jitter, pile-up near `0.9`. `judge_runs` averages a few passes; it does not remove bias.

**Crawls.** Heavy JS, PDFs, paywalls often come back thin → `fallback` + lower `evidence_quality`. Fallbacks are not written into the live crawl cache.

**Claim → URL routing.** Linked-answer script uses overlap, entity phrases, and topic hints. Prefer `mean_groundedness_factual` when framing/meta claims are present. New domains may need extra hints.

**Reporting.** Prefer MAE / RMSE / correlation on continuous support. Ternary F1 in `generate_report.py` is optional convenience.
