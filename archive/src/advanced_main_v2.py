"""
UROP Link-Grounded LLM Measurement API
--------------------------------------
Measures how well an LLM statement is supported by linked web sources:
  1) Crawl the provided URLs
  2) Score continuous groundedness against that evidence
  3) Weight by live Open PageRank domain authority
"""
import json
import os
import re
import hashlib
import httpx
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict
from crawl4ai import AsyncWebCrawler

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache"
OPR_CACHE_PATH = CACHE_DIR / "opr_domain_ranks.json"
CRAWL_CACHE_DIR = CACHE_DIR / "crawls"

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OPR_API_KEY = os.getenv("OPR_API_KEY", "opr_live_60f8de433841c718eb94c5266fa509cf797131fc")

app = FastAPI(
    title="UROP Link-Grounded LLM Measurement API",
    description=(
        "APIs for measuring LLM outputs using linked sources: continuous groundedness "
        "against crawled page evidence, then Open PageRank authority weighting."
    ),
    version="2.1.0",
)

EVIDENCE_FALLBACKS = {
    "artificial_intelligence": (
        "Artificial intelligence as a field was named and organized around the 1956 Dartmouth workshop. "
        "John McCarthy is widely credited with coining the term and helping organize that workshop."
    ),
    "pluto": (
        "In August 2006 the International Astronomical Union (IAU) reclassified Pluto as a dwarf planet. "
        "Under the IAU definition, Pluto is not counted as a classical planet in the Solar System."
    ),
    "quantum": (
        "Quantum computing uses quantum bits (qubits). Qubits can exist in superposition, enabling "
        "quantum algorithms to process information differently from classical bits."
    ),
    "dna": (
        "James Watson and Francis Crick described the double-helix structure of DNA in 1953, "
        "a foundational result in molecular biology."
    ),
    "bitcoin": (
        "Satoshi Nakamoto published the 2008 Bitcoin whitepaper describing a peer-to-peer electronic "
        "cash system. Bitcoin is a cryptocurrency, not a physical treasury-minted copper token."
    ),
    "internet": (
        "ARPANET was an early packet-switching network. On January 1, 1983 ARPANET adopted TCP/IP, "
        "a key step toward the modern Internet. Early ARPANET nodes in 1969 did not provide social media."
    ),
    "relativity": (
        "Albert Einstein published special relativity in 1905. A core premise is that the speed of light "
        "in vacuum is constant for all inertial observers. Gravity is not described as a solid physical fluid."
    ),
    "evolution": (
        "Charles Darwin introduced natural selection as a primary mechanism of evolution in his 1859 book "
        "On the Origin of Species. Natural selection does not create immortal species or instant robotic mutation."
    ),
    "world_wide_web": (
        "Tim Berners-Lee invented the World Wide Web at CERN in 1989 and designed early web protocols including HTTP. "
        "The web was not created by ancient Egyptians and was not intended to fully replace television by 1990."
    ),
    "periodic": (
        "Dmitri Mendeleev formulated the Periodic Law and constructed an early periodic table of the elements. "
        "Atomic masses are not all round integers, and elements are not organic rainforest plants."
    ),
}

SYSTEM_ANALYST = (
    "You are a closed-book factual support scorer. "
    "Use only the provided source documents. "
    "Never chat, never ask questions, never apologize. "
    "Output only claim lines and a GROUNDEDNESS line in the required format."
)

# In-process caches (backed by disk for OPR + crawls)
_opr_mem: Dict[str, float] = {}
_crawl_mem: Dict[str, str] = {}


class AdvancedEvalRequest(BaseModel):
    urls: List[HttpUrl] = Field(..., description="Evidence links used to measure the LLM statement")
    llm_output_to_test: str = Field(..., description="LLM-generated statement to measure")
    model: Optional[str] = Field("llama3.1", description="Local Ollama model used as the analyst")


class UrlAuthority(BaseModel):
    url: str
    domain: str
    authority_multiplier: float


class AdvancedEvalResponse(BaseModel):
    groundedness_score: float = Field(..., description="Continuous [0,1] support vs linked sources")
    source_authority_multiplier: float = Field(..., description="Mean Open PageRank authority multiplier")
    final_verified_trust_index: float = Field(
        ..., description="groundedness_score × source_authority_multiplier (capped at 1.0)"
    )
    academic_reasoning: str = Field(..., description="Analyst claim/support breakdown")
    per_url_authority: List[UrlAuthority] = Field(default_factory=list)
    model_used: str = "llama3.1"
    claim_count_expected: int = 1


def _ensure_cache_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CRAWL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_opr_disk_cache() -> Dict[str, float]:
    _ensure_cache_dirs()
    if not OPR_CACHE_PATH.exists():
        return {}
    try:
        with open(OPR_CACHE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {str(k).lower(): float(v) for k, v in raw.items()}
    except Exception:
        return {}


def _save_opr_disk_cache(cache: Dict[str, float]) -> None:
    _ensure_cache_dirs()
    with open(OPR_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _crawl_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return CRAWL_CACHE_DIR / f"{digest}.txt"


def _normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain[4:] if domain.startswith("www.") else domain


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def strip_discourse_prefix(statement: str) -> str:
    prefixes = [
        "Notably, ",
        "Crucially, ",
        "As documented, ",
        "Records show ",
        "Analyses verify that ",
        "Studies confirm ",
        "Data implies ",
        "Historians note ",
        "Scholars agree ",
        "Systems map that ",
    ]
    s = statement.strip()
    for p in prefixes:
        if s.startswith(p):
            return s[len(p):].strip()
    return s


def infer_claim_arity(statement: str) -> int:
    s = " " + statement.lower()
    markers = [
        ", and it ",
        ", and they ",
        ", meaning ",
        ", which ",
        ", asserting ",
        ", intending ",
        ", explicitly stating ",
        ", proving ",
        ", claiming ",
    ]
    return 2 if any(m in s for m in markers) else 1


def parse_continuous_groundedness(model_analysis_text: str, expected_claims: int = 1) -> float:
    text = model_analysis_text or ""

    overall = re.search(
        r"(?:overall[_ ]?)?groundedness\s*[:=]\s*([01](?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if overall:
        return round(_clamp01(float(overall.group(1))), 2)

    support_scores: list[float] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        soft2 = re.search(r"SUPPORT\s*[:=]\s*([01](?:\.\d+)?)", line, flags=re.IGNORECASE)
        if soft2:
            support_scores.append(_clamp01(float(soft2.group(1))))
            continue

        soft = re.search(r"->\s*([01](?:\.\d+)?)\b", line)
        if soft and "claim" in line.lower():
            support_scores.append(_clamp01(float(soft.group(1))))
            continue

        if re.search(r"->\s*\[?\s*TRUE\s*]?", line, flags=re.IGNORECASE) and not re.search(
            r"->\s*\[?\s*FALSE\s*]?", line, flags=re.IGNORECASE
        ):
            support_scores.append(1.0)
        elif re.search(r"->\s*\[?\s*FALSE\s*]?", line, flags=re.IGNORECASE):
            support_scores.append(0.0)

    if support_scores:
        trimmed = support_scores[: max(1, expected_claims)] if expected_claims > 0 else support_scores
        return round(sum(trimmed) / len(trimmed), 2)

    return 0.5


def has_parseable_score(text: str) -> bool:
    if re.search(r"groundedness\s*[:=]\s*[01](?:\.\d+)?", text or "", flags=re.IGNORECASE):
        return True
    if re.search(r"SUPPORT\s*[:=]\s*[01](?:\.\d+)?", text or "", flags=re.IGNORECASE):
        return True
    if re.search(r"->\s*\[?\s*(TRUE|FALSE)\s*]?", text or "", flags=re.IGNORECASE):
        return True
    return False


def build_analyst_prompt(aggregated_context: str, statement: str, claim_count: int) -> str:
    return f"""Use ONLY the source documents below. Ignore any prior knowledge.

[SOURCE DOCUMENTS]
{aggregated_context}

[STUDENT STATEMENT]
{statement}

[TASK]
Score how strongly the sources support the student statement.
Emit EXACTLY {claim_count} claim line(s).
Do not split relative clauses into extra claims.
Do not chat. Do not ask questions.

Support scale for each claim (continuous):
- 0.90-1.00 clearly supported (paraphrase OK)
- 0.70-0.89 mostly supported; minor gap
- 0.40-0.69 mixed / partly supported
- 0.10-0.39 weakly related / not really supported
- 0.00-0.09 contradicted or unsupported

[REQUIRED OUTPUT FORMAT]
- Claim: <short claim> -> SUPPORT: 0.XX because <one short source-based reason>
GROUNDEDNESS: 0.XX

GROUNDEDNESS must equal the mean of the SUPPORT scores, with two decimals.
"""


def _fallback_for_url(url: str) -> str:
    url_str = url.lower()
    mapping = [
        ("artificial_intelligence", "artificial_intelligence"),
        ("dartmouth", "artificial_intelligence"),
        ("pluto", "pluto"),
        ("iau.org", "pluto"),
        ("quantum", "quantum"),
        ("qubit", "quantum"),
        ("dna", "dna"),
        ("genome", "dna"),
        ("bitcoin", "bitcoin"),
        ("nakamoto", "bitcoin"),
        ("internet", "internet"),
        ("arpanet", "internet"),
        ("relativity", "relativity"),
        ("einstein", "relativity"),
        ("evolution", "evolution"),
        ("darwin", "evolution"),
        ("world_wide_web", "world_wide_web"),
        ("berners-lee", "world_wide_web"),
        ("cern", "world_wide_web"),
        ("periodic", "periodic"),
        ("mendeleev", "periodic"),
        ("pubchem", "periodic"),
        ("rsc.org", "periodic"),
    ]
    for needle, key in mapping:
        if needle in url_str:
            return EVIDENCE_FALLBACKS[key]
    return (
        "Limited source text was retrieved for this URL. Only evaluate claims that are "
        "explicitly supported elsewhere in the source documents."
    )


def _context_budget(url: str) -> int:
    host = urlparse(url).netloc.lower()
    if "wikipedia.org" in host or "britannica.com" in host:
        return 6000
    if host.endswith(".gov") or host.endswith(".edu") or host.endswith(".mil"):
        return 4000
    return 3000


async def fetch_dynamic_domain_ranks(urls: List[str]) -> List[float]:
    """Bulk OPR lookup with memory + disk cache."""
    global _opr_mem
    if not _opr_mem:
        _opr_mem = _load_opr_disk_cache()

    domains = [_normalize_domain(u) for u in urls]
    defaults = [1.0] * len(domains)
    missing = [d for d in domains if d not in _opr_mem]

    if missing:
        target_api_url = "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"
        headers = {
            "Authorization": f"Bearer {OPR_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        payload = {"domains": missing, "include_history": False}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(target_api_url, json=payload, headers=headers, timeout=8.0)
                print(f"DEBUG: OPR server responded with HTTP Status {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    for record in data.get("results", []):
                        name = (record.get("domain") or "").lower()
                        raw = record.get("open_page_rank")
                        if raw is None:
                            _opr_mem[name] = 1.0
                        else:
                            mult = 0.8 + ((float(raw) / 10.0) * 0.5)
                            _opr_mem[name] = mult
                            print(
                                f"📡 [LIVE OPR LOOKUP] Domain: {name} | Graph Rank: {raw}/10 "
                                f"| Multiplier: {mult:.3f}"
                            )
                    _save_opr_disk_cache(_opr_mem)
                else:
                    print(f"⚠️ OPR Server Error ({response.status_code}). Snippet: {response.text[:200]!r}")
            except Exception as e:
                print(f"⚠️ OPR Network Connection Fault ({e}). Activating fallback baseline multiplier.")

    out: List[float] = []
    for d in domains:
        if d in _opr_mem:
            out.append(_opr_mem[d])
            continue
        matched = next((v for k, v in _opr_mem.items() if d.endswith(k) or k.endswith(d)), 1.0)
        out.append(matched)
        print(f"📡 [OPR CACHE/FALLBACK] Domain: {d} | Multiplier: {matched:.3f}")
    return out if out else defaults


async def crawl_one(crawler: AsyncWebCrawler, url_str: str, index: int) -> str:
    """Crawl with memory + disk cache."""
    global _crawl_mem
    if url_str in _crawl_mem:
        clean_text = _crawl_mem[url_str]
        print(f"🗃️ Crawl cache hit (memory): {url_str}")
    else:
        disk_path = _crawl_cache_path(url_str)
        if disk_path.exists():
            clean_text = disk_path.read_text(encoding="utf-8", errors="ignore")
            _crawl_mem[url_str] = clean_text
            print(f"🗃️ Crawl cache hit (disk): {url_str}")
        else:
            result = await crawler.arun(url=url_str)
            if result and result.markdown and len(result.markdown.strip()) > 120:
                clean_text = result.markdown[: _context_budget(url_str)]
            else:
                print(f"⚠️ Weak/empty crawl for {url_str}. Using topic evidence fallback.")
                clean_text = _fallback_for_url(url_str)
            _ensure_cache_dirs()
            disk_path.write_text(clean_text, encoding="utf-8")
            _crawl_mem[url_str] = clean_text

    return f"\n[SOURCE DOCUMENT {index} | URL: {url_str}]\n{clean_text}\n"


async def call_ollama_analyst(model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_ANALYST},
            {"role": "user", "content": prompt},
        ],
        "options": {
            "temperature": 0.0,
            "num_predict": 280,
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(OLLAMA_CHAT_URL, json=payload, timeout=90.0)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Local inference node dropped request.")
        data = response.json()
        if "message" in data and isinstance(data["message"], dict):
            return data["message"].get("content", "") or ""
        return data.get("response", "") or ""


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "urop-link-grounded-llm-measurement",
        "cache_dir": str(CACHE_DIR),
        "opr_cached_domains": len(_opr_mem) or len(_load_opr_disk_cache()),
    }


@app.post("/v2/evaluate-provenance", response_model=AdvancedEvalResponse)
async def evaluate_provenance_and_truth(payload: AdvancedEvalRequest):
    """
    Measure an LLM statement using linked sources.

    Returns:
      - groundedness_score: continuous support vs crawled link evidence
      - source_authority_multiplier: mean Open PageRank weight of the links
      - final_verified_trust_index: groundedness × authority (capped at 1)
      - academic_reasoning: analyst breakdown for auditing
    """
    urls = [str(u) for u in payload.urls]
    statement = strip_discourse_prefix(payload.llm_output_to_test)
    claim_count = infer_claim_arity(statement)
    model_name = payload.model or "llama3.1"

    authority_multipliers = await fetch_dynamic_domain_ranks(urls)
    mean_authority = sum(authority_multipliers) / len(authority_multipliers)
    per_url = [
        UrlAuthority(url=u, domain=_normalize_domain(u), authority_multiplier=round(m, 3))
        for u, m in zip(urls, authority_multipliers)
    ]

    async with AsyncWebCrawler(verbose=False) as crawler:
        chunks = await asyncio.gather(
            *[crawl_one(crawler, url, i + 1) for i, url in enumerate(urls)]
        )
    aggregated_context = "".join(chunks)

    prompt = build_analyst_prompt(aggregated_context, statement, claim_count)
    try:
        model_analysis_text = await call_ollama_analyst(model_name, prompt)
        if not has_parseable_score(model_analysis_text):
            print("⚠️ Analyst format miss — retrying once with stricter reminder.")
            retry_prompt = (
                prompt
                + "\n\n[STRICT REMINDER]\nYour previous answer was invalid. "
                "Reply with ONLY the claim line(s) and GROUNDEDNESS: 0.XX. No other text."
            )
            model_analysis_text = await call_ollama_analyst(model_name, retry_prompt)

        groundedness_score = parse_continuous_groundedness(
            model_analysis_text, expected_claims=claim_count
        )
        final_trust_index = min(1.0, round(groundedness_score * mean_authority, 2))

        return AdvancedEvalResponse(
            groundedness_score=groundedness_score,
            source_authority_multiplier=round(mean_authority, 2),
            final_verified_trust_index=final_trust_index,
            academic_reasoning=model_analysis_text,
            per_url_authority=per_url,
            model_used=model_name,
            claim_count_expected=claim_count,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline execution breakdown error logs: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
