# LinkGround — Developer Guide

This document explains **what LinkGround is, what each part does, how a request flows through the system, why the architecture looks this way, and what we deliberately did *not* do**. It is written as an internal developer reference for the UROP / methods-paper track (LCSE).

For short ops notes see `docs/DEVELOPMENT.md`. For the research claim see `docs/RESEARCH.md` and `docs/PAPER_ROADMAP.md`. For the HTTP contract see `docs/API.md`.

---

## 1. What this project actually is

LinkGround is a **small FastAPI experiment harness** that answers one question:

> Given a student / LLM *statement* and one or more *cited URLs*, how strongly do the **crawled contents of those pages** support the statement?

That continuous score is `groundedness_score` (we also call it **support**).

Separately, we look up how “prestigious” those domains are on the open web (Open PageRank) and report that as `authority_multiplier`. We then form a secondary product-style quantity:

```text
trust_index = min(1.0, groundedness_score × mean_authority)
```

**The research thesis (LCSE — Link-Conditioned Support Estimation)** is that many “groundedness / trust” systems quietly fuse *textual support* with *web prestige*. That fusion is dangerous: a famous false claim cited to Wikipedia can look “trusted,” and a true claim cited to the wrong page can look fine if the model already “knows” the fact. LCSE keeps the signals separate and stresses the system with **citation swaps** (same text, wrong URL).

So:

| Layer | Role |
|---|---|
| FastAPI `/v1/evaluate` | Runnable scoring API (the lab instrument) |
| `data/lcse/` + paper benchmark | Controlled experiments |
| `results/` | Frozen numbers for the paper |
| Prestige / trust_index | Secondary; never redefine “support” |

This is **not** a production citation checker, a search engine, or an open-web fact verifier. It is a methods stack for studying link-conditioned support.

---

## 2. Repository map

```text
urop/
  linkground/                 # The service
    api/                      # HTTP + Pydantic models
    services/                 # Crawl, OPR, judge, discovery, scoring
    config.py                 # Env + constants
    __main__.py               # `python -m linkground`
  scripts/                    # Dataset build, benchmark, LCSE suite, EG eval
  data/
    paper_benchmark.jsonl     # 50 long-answer paper cases
    lcse/                     # Short suite: swaps / confound / ethics
  results/                    # Metrics, plots, EG/LCSE JSON (mostly gitignored)
  docs/                       # Research + engineering notes
  examples/                   # Free-form EG1/EG2 answers + URL pools
  .cache/                     # Crawl + OPR caches (gitignored)
  .env / .env.example         # Secrets and tuning
```

**Convention:** business logic lives in `linkground/services/`. Routes only orchestrate. Datasets live under `data/`. Anything you would cite in a paper goes under `results/` (or is summarized in `results/COMPARISON.md`).

---

## 3. The two scores (and why they are not one score)

### 3.1 Support = `groundedness_score`

- Range roughly `[0, 1]`.
- Means: “do the **provided source documents** license this claim?”
- Produced by an LLM **judge** that is instructed to be **closed-book**: only `[SOURCE DOCUMENTS]` count; prior knowledge is forbidden; URLs written inside the student statement are ignored.
- Then multiplied by crawl quality and discovery discounts (see §5).

### 3.2 Prestige = `authority_multiplier`

- Derived from Open PageRank domain ranks.
- Means: “how central / popular is this domain on the web?”
- **Not** a truth signal. A high-OPR page can still fail to support a claim.

### 3.3 `trust_index` and `inflation`

```text
trust_index = min(1, support × prestige)
inflation   = max(0, trust_index − support)
```

Inflation is how much prestige *inflates* the fused trust number above raw support. Flags like `high_prestige_low_support` exist so the paper can talk about prestige masking weak evidence.

**Why not bake prestige into the primary score?**  
Because then citation swaps and soft-wrong-on-Wikipedia become uninterpretable: you cannot tell whether the system read the page or merely liked the domain. Keeping them separate is the whole point of LCSE.

---

## 4. End-to-end: what happens on `POST /v1/evaluate`

Entry point: `evaluate()` in `linkground/api/routes.py`.

```text
Request (statement + urls? + options)
    │
    ├─ strip discourse prefixes ("Notably,", …)
    ├─ claim_count = request.claim_count OR infer from text
    │
    ├─ [optional] discover URLs (Wikipedia + trusted-domain BFS)
    ├─ merge caller URLs + discovered URLs
    │     └─ 422 if still empty
    │
    ├─ Open PageRank → per-URL authority multipliers
    ├─ Crawl each URL → live | cache | fallback text
    │     └─ [optional] crawl rescue if every caller page is fallback
    │
    ├─ Format evidence block for the judge
    │     (tags: EVIDENCE_SOURCE, ORIGIN, WEIGHT)
    │
    ├─ Judge LLM → SUPPORT lines + GROUNDEDNESS
    │     └─ parse_groundedness (mean SUPPORT if claim_count ≥ 2)
    │
    ├─ groundedness = raw × evidence_quality × discovery_weight
    ├─ trust_index  = min(1, groundedness × mean_authority)
    └─ research block (support, prestige, inflation, source, flags)
```

### 4.1 Request fields that matter

| Field | Meaning |
|---|---|
| `statement` | The claim / LLM answer text to score |
| `urls` | Evidence pages. Empty → discovery turns on |
| `claim_count` | Force N claim lines (mixed cases use `2`) |
| `discover_evidence` | Find allowlisted pages when cites are missing |
| `judge_runs` | Average multiple judge passes |
| `model` | Judge model id (LLM7 / Groq / Ollama) |

### 4.2 Evidence acquisition (`services/crawler.py`)

For each URL we try, in order:

1. In-memory / disk crawl cache (TTL from `CACHE_TTL_SECONDS`)
2. Live crawl (`crawl4ai` / AsyncWebCrawler)
3. If the page is too thin (JS shell, PDF wall, etc.) → **topic fallback** text from `services/evidence.py`, marked `EVIDENCE_SOURCE: fallback`

Fallbacks are intentionally **not** treated as first-class live evidence: `evidence_quality` drops (all-fallback → `FALLBACK_EVIDENCE_FACTOR`, default `0.6`).

**Crawl rescue:** if the caller supplied URLs but every crawl is fallback, the pipeline may auto-discover trusted pages and mix them in (`crawl_rescue_mixed`). That keeps the API usable when Wikipedia is temporarily blocked, but it can **confound** “caller-only citation” experiments — watch the `notes` / `evidence_mode` fields.

### 4.3 Discovery (`services/discovery.py`)

Discovery is **not** open web search. It is:

1. Wikipedia API search for the statement
2. BFS expansion along links, restricted to `trusted_sources.TRUSTED_DOMAINS`

Why this way: reproducible, safer, and aligned with “reference-like” sources for a methods paper.  
Why not Google/Bing: ranking noise, ToS, non-reproducible SERPs, and it would blur “cited page” vs “whatever the search engine liked.”

Discovered evidence is discounted (`DISCOVERY_SCORE_FACTOR`, default `0.55`) so “we found a good page for you” does not silently replace attribution.

### 4.4 Prestige (`services/authority.py`)

Bulk Open PageRank lookup → map rank to a multiplier roughly in `[AUTHORITY_BASE, AUTHORITY_BASE+AUTHORITY_SCALE]` (defaults `0.8` + `0.5`). Missing key / miss → neutral `1.0`. Cached under `.cache/opr_domain_ranks.json`.

### 4.5 The judge (`services/analyst.py` + `scoring.py`)

The judge is an OpenAI-compatible chat call when `JUDGE_BASE_URL` is set (LLM7 or Groq); otherwise local Ollama.

**Prompt contract (important):**

- Use **only** `[SOURCE DOCUMENTS]`.
- Ignore URLs / `Source:` lines inside the student statement.
- If the documents are about a different topic than the claim, SUPPORT must be ≤ `0.10`.
- Emit exactly `claim_count` claim lines with continuous SUPPORT in `[0, 1]`.
- `GROUNDEDNESS` should equal the mean of SUPPORT scores.

**Parsing:** `parse_groundedness` in `scoring.py`. When `expected_claims >= 2` (mixed), we **mean the SUPPORT lines** and do not trust a single inflated `GROUNDEDNESS` line. That fixed a failure mode where mixed answers scored ~0.9 because the true half dominated a holistic score.

**Claim count inference:** markers like `" however, "`, `", which "`, etc. force 2 claims. Paper `mixed` cases also set `claim_count: 2` explicitly in the dataset so we are not relying on heuristics alone.

### 4.6 Final composition

```text
raw_support        ← judge
evidence_quality   ← live/cache vs fallback mix
discovery_weight   ← caller vs discovered mix
groundedness_score = round(raw × quality × weight, 2)
trust_index        = min(1, round(groundedness × mean_authority, 2))
```

Response also returns per-URL evidence provenance, authority breakdown, judge reasoning text, and the `research` object used in analysis notebooks / paper tables.

---

## 5. Design decisions: why this way (and why not the alternatives)

### 5.1 Closed-book, document-conditioned scoring

**Why:** We are measuring *attribution*, not world knowledge. A model that says “Pluto is a dwarf planet” while looking at the Colosseum page should score near zero for *support by this link*, even though the fact is famous.

**Why not open-book fact checking:** That collapses to “is the claim true?”, which citation swaps cannot stress. The paper would no longer be about link conditioning.

### 5.2 URLs live only in `urls[]`, never in the statement body

Early paper cases embedded `Source: https://…` inside the statement. The judge (and sometimes the crawl path) treated that as a leak: swapped URL in `urls[]` but correct URL in the text → high scores, **swap Δ ≈ 0**.

**Fix:** `build_paper_dataset.strip_urls_from_statement`. Supported and swapped pairs share **identical** claim text; only `urls[]` differs.

**Why not keep inline citations “for realism”:** Real answers do cite URLs in text, but for *this experiment* that confound destroys the independent variable (which page was provided as evidence).

### 5.3 Continuous support, not a classifier-first product

The API returns a continuous score. Ternary labels (`False / Partial / True`) are a **reporting convenience** for accuracy / precision / recall / F1:

| Bin | Score range |
|---|---|
| False | ≤ 0.25 |
| Partial | ≤ 0.75 |
| True | > 0.75 |

**Why not optimize F1 as primary:** Continuous MAE and swap Δ answer the research questions directly. F1 is sensitive to bin edges and to score pile-up near `0.0` / `0.9`. We still report ternary metrics as secondary (`scripts/generate_report.py`).

### 5.4 Mixed answers force two claim lines

A single GROUNDEDNESS over a true+false paragraph tends to stay high. Forcing two SUPPORT lines and averaging them makes the false half visible (target ~0.5).

### 5.5 Allowlisted discovery, not open retrieval

Engineering + ethics choice: reproducible English reference domains, disclosed bias (`docs/LIMITATIONS.md`). Not a claim that “trusted domain ⇒ true.”

### 5.6 Fallbacks instead of hard fail on crawl miss

Without fallbacks, many Wikipedia/JS pages would 500 the pipeline and wipe experiments. With fallbacks, we keep running but **mark and discount** the evidence. Prefer live crawl when possible.

### 5.7 Local Ollama for claim *splitting*, remote LLM for *judging*

Long free-form answers (EG1/EG2) are split into claims with local `llama3.1` (`LOCAL_SPLIT_MODEL`) for JSON control and cost, then each claim is scored through the API judge (LLM7 Nemo for case studies). Suite tables on disk may still be from an earlier Groq freeze — see `docs/PAPER_ROADMAP.md`.

### 5.8 Why FastAPI instead of a notebook-only pipeline

The same scoring path must be callable from:

- interactive `/docs`
- `run_benchmark.py`
- `run_lcse_suite.py`
- `evaluate_linked_answer.py` / `rescore_linked_eval.py`

A single HTTP instrument keeps experiment code from forking five incompatible prompt stacks.

---

## 6. Datasets and experiments

### 6.1 Paper long-answer benchmark (50 cases)

Built by `scripts/build_paper_dataset.py` → `data/paper_benchmark.jsonl`.

10 topics × 5 conditions:

| Condition | What we test |
|---|---|
| `supported` | True long answer + matching URL |
| `swapped` | Same text as supported + unrelated URL |
| `unsupported` | Blatantly false + on-topic URL |
| `soft_wrong` | Related but wrong claim on a prestige page (mid label) |
| `mixed` | True half + false half; `claim_count=2` |

Primary analysis:

1. **MAE by condition**
2. **Citation-swap delta** = `groundedness(supported) − groundedness(swapped)` per `pair_id`

Pipeline:

```powershell
python scripts/build_paper_dataset.py
python -m linkground
python scripts/run_benchmark.py --sleep 2
python scripts/generate_report.py
```

Outputs: `results/benchmark_metrics.csv`, `metrics_report.txt`, MAE/swap/F1 plots, confusion matrix.

### 6.2 LCSE short suite (`data/lcse/`)

| File | Experiment |
|---|---|
| `citation_swap.jsonl` | Lead result: matched vs swapped |
| `confound_grid.jsonl` | Support × prestige cells (SH/SL/UH/UL) |
| `ethics_audit.jsonl` | Caller vs discovery disclosure |

Runner: `scripts/run_lcse_suite.py`.

### 6.3 EG1 / EG2 case studies

Free-form answers in `examples/`, split + scored, then optionally re-scored with `rescore_linked_eval.py` onto the frozen judge stack without re-splitting.

---

## 7. Metrics glossary (what the report means)

| Metric | Meaning |
|---|---|
| **MAE (overall / by condition)** | mean \|predicted support − `label_support`\| |
| **Swap delta** | How much support drops when the URL is wrong (higher is better attribution) |
| **Pearson / Spearman** | Correlation of predicted vs expected continuous support |
| **Accuracy / Precision / Recall / F1** | Ternary classification after binning (secondary) |
| **Support (in sklearn report)** | Number of *true* examples in that class — not the groundedness score |
| **trust_mae** | MAE if you (mistakenly) treated `trust_index` as the support label |
| **mean_inflation** | Average prestige inflation over the run |

Current failure signature on long-answer swaps: supported stays high, but many swapped rows also stay high → low swap delta vs the short LCSE suite (~0.87). That is mostly **parametric leakage** in the judge, not a dataset URL-leak anymore.

---

## 8. Configuration

Copy `.env.example` → `.env`. Important knobs:

| Variable | Role |
|---|---|
| `OPR_API_KEY` | Live prestige |
| `JUDGE_BASE_URL` / `JUDGE_API_KEY` | LLM7 or Groq; empty → Ollama |
| `DEFAULT_ANALYST_MODEL` | e.g. `mistral-Nemo-Instruct-2407` |
| `JUDGE_MAX_TOKENS` | Cap judge completion length |
| `LOCAL_SPLIT_MODEL` | Ollama model for claim splitting |
| `EVIDENCE_CHAR_BUDGET` | How much page text the judge sees |
| `FALLBACK_EVIDENCE_FACTOR` | Penalty when evidence is stub/fallback |
| `DISCOVERY_SCORE_FACTOR` | Penalty for discovered (non-caller) URLs |
| `CACHE_TTL_SECONDS` | Crawl cache lifetime |

`linkground/config.py` loads dotenv with override so `.env` wins over leftover shell env vars.

---

## 9. Known failure modes (honest)

1. **Parametric knowledge on swaps** — Judge endorses famous claims against off-topic pages despite the prompt. Dominant remaining error on the paper benchmark.
2. **Soft-wrong too hard-zero** — Mid labels needed for prestige-inflation stories; hard zeros make `trust_index = 0` and hide inflation.
3. **Crawl rescue / discovery mixing** — Can change evidence under the feet of a “caller URL only” experiment.
4. **Score pile-up** — Many scores near `0.0` or `~0.9` → Partial class recall suffers; ternary F1 looks worse than continuous MAE.
5. **Allowlist / English bias** — Discovery is not a global web oracle.
6. **Thin pages / PDFs / paywalls** — Fallbacks + quality discount; judge may under- or over-use stubs.

Planned hardening directions (not all implemented): topic-overlap gate before the LLM, require verbatim quote spans from the docs in the `because` clause, stricter swap URL selection, multi-run median, disable crawl rescue during swap benchmarks.

---

## 10. How to run locally

```powershell
cd c:\Users\sathw\Desktop\urop
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# fill OPR_API_KEY, JUDGE_*, DEFAULT_ANALYST_MODEL

python -m linkground
# http://127.0.0.1:8000/docs
```

If port 8000 is stuck: find the PID with `Get-NetTCPConnection -LocalPort 8000` and stop that process.

Contributor rules of thumb:

1. Do not fold prestige into `groundedness_score`.
2. Keep experiment logic reproducible (datasets in `data/`, outputs in `results/`).
3. Prefer continuous MAE + swap delta when claiming progress; treat F1 as secondary.
4. When changing the judge prompt, restart the API process — it loads prompts at import time.

---

## 11. Mental model in one paragraph

LinkGround is a **closed-book support estimator conditioned on whatever pages you hand it**, with a separate prestige channel for analysis. The API exists so every experiment — short LCSE swaps, long paper answers, EG case studies — hits the **same** crawl → judge → parse path. The architecture favors interpretability of *attribution failures* over maximizing a single fused “trust” number or a ternary F1 score.
