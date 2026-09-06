"""HTTP routes for LinkGround."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from linkground import __version__
from linkground.api.schemas import EvaluateRequest, EvaluateResponse, UrlAuthority
from linkground.config import CACHE_DIR
from linkground.services.analyst import score_statement
from linkground.services.authority import fetch_authority_multipliers, normalize_domain
from linkground.services.crawler import aggregate_source_context
from linkground.services.scoring import infer_claim_count, strip_discourse_prefix

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "linkground",
        "version": __version__,
        "cache_dir": str(CACHE_DIR),
    }


@router.post("/v1/evaluate", response_model=EvaluateResponse)
@router.post("/v2/evaluate-provenance", response_model=EvaluateResponse, include_in_schema=False)
async def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    """
    Measure an LLM statement using linked sources.

    Pipeline:
      1. Resolve Open PageRank authority for each URL
      2. Crawl and aggregate page evidence
      3. Score continuous groundedness with a local analyst model
      4. Combine into a trust index
    """
    urls = [str(url) for url in payload.urls]
    statement = strip_discourse_prefix(payload.statement)
    claim_count = infer_claim_count(statement)
    model_name = payload.model or "llama3.1"

    try:
        authority_scores = await fetch_authority_multipliers(urls)
        mean_authority = sum(authority_scores) / len(authority_scores)
        per_url = [
            UrlAuthority(
                url=url,
                domain=normalize_domain(url),
                authority_multiplier=round(score, 3),
            )
            for url, score in zip(urls, authority_scores)
        ]

        source_context = await aggregate_source_context(urls)
        groundedness, reasoning = await score_statement(
            source_context=source_context,
            statement=statement,
            claim_count=claim_count,
            model_name=model_name,
        )
        trust_index = min(1.0, round(groundedness * mean_authority, 2))

        return EvaluateResponse(
            groundedness_score=groundedness,
            authority_multiplier=round(mean_authority, 2),
            trust_index=trust_index,
            analyst_reasoning=reasoning,
            per_url_authority=per_url,
            model_used=model_name,
            claim_count=claim_count,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Evaluation pipeline failed: {exc}") from exc
