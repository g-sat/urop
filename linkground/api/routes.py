from __future__ import annotations

from fastapi import APIRouter, HTTPException

from linkground import __version__
from linkground.api.schemas import (
    DiscoveredUrlItem,
    EvaluateRequest,
    EvaluateResponse,
    EvidenceItem,
    UrlAuthority,
)
from linkground.config import CACHE_DIR, FALLBACK_EVIDENCE_FACTOR
from linkground.services.analyst import score_statement
from linkground.services.authority import fetch_authority_multipliers, normalize_domain
from linkground.services.crawler import collect_evidence, format_evidence_block
from linkground.services.discovery import discover_evidence_urls
from linkground.services.reporting import build_research_block
from linkground.services.scoring import infer_claim_count, strip_discourse_prefix
from linkground.services.weights import evidence_origin_weight

router = APIRouter()


def _evidence_quality(sources: list[str]) -> float:
    if not sources:
        return 0.0
    usable = sum(1 for s in sources if s in {"live", "cache"})
    ratio = usable / len(sources)
    if ratio == 1.0:
        return 1.0
    if ratio == 0.0:
        return FALLBACK_EVIDENCE_FACTOR
    return round(FALLBACK_EVIDENCE_FACTOR + (1.0 - FALLBACK_EVIDENCE_FACTOR) * ratio, 3)


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "linkground",
        "version": __version__,
        "cache_dir": str(CACHE_DIR),
    }


@router.get("/v1/trusted-domains")
async def trusted_domains() -> dict:
    from linkground.services.trusted_sources import TRUSTED_DOMAINS, TRUSTED_SEED_URLS

    return {
        "domains": sorted(TRUSTED_DOMAINS),
        "seed_urls": list(TRUSTED_SEED_URLS),
    }


@router.post("/v1/evaluate", response_model=EvaluateResponse)
@router.post("/v2/evaluate-provenance", response_model=EvaluateResponse, include_in_schema=False)
async def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    caller_urls = [str(u) for u in payload.urls]
    statement = strip_discourse_prefix(payload.statement)
    claim_count = payload.claim_count if payload.claim_count is not None else infer_claim_count(statement)
    model_name = payload.model or "llama3.1"
    discovered_items: list[DiscoveredUrlItem] = []
    discovered_set: set[str] = set()

    try:
        if payload.discover_evidence or not caller_urls:
            found = await discover_evidence_urls(
                statement,
                max_urls=payload.max_discovered_urls,
                depth=payload.discovery_depth,
            )
            discovered_items = [
                DiscoveredUrlItem(
                    url=item.url,
                    score=round(item.score, 3),
                    origin=item.origin,
                    title=item.title,
                )
                for item in found
            ]
            discovered_set = {item.url for item in discovered_items}

        urls = list(caller_urls)
        if payload.discover_evidence or not caller_urls:
            for item in discovered_items:
                if item.url not in urls:
                    urls.append(item.url)

        if not urls:
            raise HTTPException(status_code=422, detail="No evidence URLs found")

        caller_set = set(caller_urls)
        n_caller = sum(1 for u in urls if u in caller_set)
        n_discovered = sum(1 for u in urls if u in discovered_set and u not in caller_set)

        if n_caller and n_discovered:
            evidence_mode = "mixed"
        elif n_discovered:
            evidence_mode = "discovered"
        else:
            evidence_mode = "caller"
            discovered_items = []
            discovered_set = set()

        origin_by_url = {u: ("caller" if u in caller_set else "discovered") for u in urls}
        authority_scores = await fetch_authority_multipliers(urls)
        mean_authority = sum(authority_scores) / len(authority_scores)
        per_url = [
            UrlAuthority(url=u, domain=normalize_domain(u), authority_multiplier=round(s, 3))
            for u, s in zip(urls, authority_scores)
        ]

        documents = await collect_evidence(urls)
        quality = _evidence_quality([doc.source for doc in documents])
        crawl_rescued = False

        # If every caller page failed to crawl, supplement from trusted discovery.
        if (
            caller_urls
            and not discovered_set
            and quality <= FALLBACK_EVIDENCE_FACTOR
            and all(doc.source == "fallback" for doc in documents)
        ):
            found = await discover_evidence_urls(
                statement,
                max_urls=payload.max_discovered_urls,
                depth=payload.discovery_depth,
            )
            for item in found:
                if item.url not in urls:
                    urls.append(item.url)
                    discovered_set.add(item.url)
                    discovered_items.append(
                        DiscoveredUrlItem(
                            url=item.url,
                            score=round(item.score, 3),
                            origin=item.origin,
                            title=item.title,
                        )
                    )
            if discovered_set:
                crawl_rescued = True
                n_caller = sum(1 for u in urls if u in caller_set)
                n_discovered = sum(1 for u in urls if u in discovered_set and u not in caller_set)
                evidence_mode = "mixed" if n_caller and n_discovered else ("discovered" if n_discovered else "caller")
                origin_by_url = {u: ("caller" if u in caller_set else "discovered") for u in urls}
                authority_scores = await fetch_authority_multipliers(urls)
                mean_authority = sum(authority_scores) / len(authority_scores)
                per_url = [
                    UrlAuthority(url=u, domain=normalize_domain(u), authority_multiplier=round(s, 3))
                    for u, s in zip(urls, authority_scores)
                ]
                documents = await collect_evidence(urls)
                quality = _evidence_quality([doc.source for doc in documents])

        source_context = format_evidence_block(documents, origin_by_url=origin_by_url)
        evidence_items = [
            EvidenceItem(
                url=doc.url,
                source=doc.source,
                char_count=doc.char_count,
                usable=doc.source in {"live", "cache"},
                origin=origin_by_url.get(doc.url, "caller"),
            )
            for doc in documents
        ]
        weight = evidence_origin_weight(
            evidence_mode,
            caller_url_count=n_caller,
            discovered_url_count=n_discovered,
        )

        raw, reasoning, judge_std = await score_statement(
            source_context=source_context,
            statement=statement,
            claim_count=claim_count,
            model_name=model_name,
            judge_runs=payload.judge_runs,
        )
        groundedness = round(raw * quality * weight, 2)
        trust = min(1.0, round(groundedness * mean_authority, 2))

        notes: list[str] = []
        if evidence_mode != "caller":
            notes.append(f"discovery weight={weight}")
        if quality < 1.0:
            notes.append(f"weak crawl evidence_quality={quality}")
        if crawl_rescued:
            notes.append("crawl_rescue_mixed")
        if judge_std is not None:
            notes.append(f"judge_std={judge_std}")

        research = build_research_block(
            evidence_mode=evidence_mode,
            discovery_weight=weight,
            groundedness_score=groundedness,
            authority_multiplier=round(mean_authority, 2),
            trust_index=trust,
            caller_url_count=n_caller,
            discovered_url_count=n_discovered,
        )

        return EvaluateResponse(
            groundedness_score=groundedness,
            authority_multiplier=round(mean_authority, 2),
            trust_index=trust,
            analyst_reasoning=reasoning,
            per_url_authority=per_url,
            evidence=evidence_items,
            evidence_quality=quality,
            evidence_mode=evidence_mode,
            discovery_weight=weight,
            discovered_urls=discovered_items,
            judge_std=judge_std,
            model_used=model_name,
            claim_count=claim_count,
            notes=notes,
            research=research,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
