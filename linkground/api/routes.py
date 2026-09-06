from __future__ import annotations
from fastapi import APIRouter, HTTPException
from linkground import __version__
from linkground.api.schemas import DiscoveredUrlItem, EvaluateRequest, EvaluateResponse, EvidenceItem, UrlAuthority
from linkground.config import CACHE_DIR, DISCOVERY_SCORE_FACTOR, FALLBACK_EVIDENCE_FACTOR
from linkground.services.analyst import score_statement
from linkground.services.authority import fetch_authority_multipliers, normalize_domain
from linkground.services.crawler import collect_evidence, format_evidence_block
from linkground.services.discovery import discover_evidence_urls
from linkground.services.scoring import infer_claim_count, strip_discourse_prefix
from linkground.services.weights import evidence_origin_weight
from linkground.services.reporting import build_research_block
router = APIRouter()

def _evidence_quality(sources: list[str]) -> float:
    if not sources:
        return 0.0
    usable = sum((1 for source in sources if source in {'live', 'cache'}))
    ratio = usable / len(sources)
    if ratio == 1.0:
        return 1.0
    if ratio == 0.0:
        return FALLBACK_EVIDENCE_FACTOR
    return round(FALLBACK_EVIDENCE_FACTOR + (1.0 - FALLBACK_EVIDENCE_FACTOR) * ratio, 3)

@router.get('/health')
async def health() -> dict:
    return {'status': 'ok', 'service': 'linkground', 'version': __version__, 'cache_dir': str(CACHE_DIR)}

@router.get('/v1/trusted-domains')
async def trusted_domains() -> dict:
    from linkground.services.trusted_sources import TRUSTED_DOMAINS, TRUSTED_SEED_URLS
    return {
        "domains": sorted(TRUSTED_DOMAINS),
        "seed_urls": list(TRUSTED_SEED_URLS),
        "note": "Allowlist for discovery only. Not a truth oracle.",
    }


@router.post('/v1/evaluate', response_model=EvaluateResponse)
@router.post('/v2/evaluate-provenance', response_model=EvaluateResponse, include_in_schema=False)
async def evaluate(payload: EvaluateRequest) -> EvaluateResponse:
    caller_urls = [str(url) for url in payload.urls]
    statement = strip_discourse_prefix(payload.statement)
    claim_count = infer_claim_count(statement)
    model_name = payload.model or 'llama3.1'
    discovered_items: list[DiscoveredUrlItem] = []
    discovered_set: set[str] = set()
    try:
        if payload.discover_evidence or not caller_urls:
            found = await discover_evidence_urls(statement, max_urls=payload.max_discovered_urls, depth=payload.discovery_depth)
            discovered_items = [DiscoveredUrlItem(url=item.url, score=round(item.score, 3), origin=item.origin, title=item.title) for item in found]
            discovered_set = {item.url for item in discovered_items}
        urls = list(caller_urls)
        if payload.discover_evidence or not caller_urls:
            for item in discovered_items:
                if item.url not in urls:
                    urls.append(item.url)
        if not urls:
            raise HTTPException(status_code=422, detail='No evidence URLs available. Provide urls or enable discover_evidence so trusted seeds can be searched.')
        n_caller = sum((1 for url in urls if url in set(caller_urls)))
        caller_set = set(caller_urls)
        n_discovered = sum((1 for url in urls if url in discovered_set and url not in caller_set))
        if n_caller and n_discovered:
            evidence_mode = 'mixed'
        elif n_discovered and (not n_caller):
            evidence_mode = 'discovered'
        else:
            evidence_mode = 'caller'
            discovered_items = []
            discovered_set = set()
        origin_by_url = {url: 'caller' if url in caller_set else 'discovered' for url in urls}
        authority_scores = await fetch_authority_multipliers(urls)
        mean_authority = sum(authority_scores) / len(authority_scores)
        per_url = [UrlAuthority(url=url, domain=normalize_domain(url), authority_multiplier=round(score, 3)) for url, score in zip(urls, authority_scores)]
        documents = await collect_evidence(urls)
        source_context = format_evidence_block(documents, origin_by_url=origin_by_url)
        evidence_items = [EvidenceItem(url=doc.url, source=doc.source, char_count=doc.char_count, usable=doc.source in {'live', 'cache'}, origin=origin_by_url.get(doc.url, 'caller')) for doc in documents]
        quality = _evidence_quality([doc.source for doc in documents])
        origin_weight = evidence_origin_weight(evidence_mode, caller_url_count=n_caller, discovered_url_count=n_discovered)
        raw_groundedness, reasoning, judge_std = await score_statement(source_context=source_context, statement=statement, claim_count=claim_count, model_name=model_name, judge_runs=payload.judge_runs)
        groundedness = round(raw_groundedness * quality * origin_weight, 2)
        trust_index = min(1.0, round(groundedness * mean_authority, 2))
        notes: list[str] = ['groundedness_score is authority-agnostic; prefer it over trust_index for factual support.', 'authority_multiplier / trust_index use Open PageRank popularity, not correctness.']
        if evidence_mode == 'discovered':
            notes.append(f'Evidence was auto-discovered (no caller links). Score multiplied by discovery_weight={origin_weight} (DISCOVERY_SCORE_FACTOR={DISCOVERY_SCORE_FACTOR}) so wrong finds cannot dominate results.')
        elif evidence_mode == 'mixed':
            notes.append(f'Mixed caller + discovered evidence. Score multiplied by discovery_weight={origin_weight} (caller links count fully; discovered links count at factor {DISCOVERY_SCORE_FACTOR}).')
        if quality < 1.0:
            notes.append(f'Weak crawl evidence detected (evidence_quality={quality}); score was soft-penalized because one or more URLs used fallback text.')
        if judge_std is not None:
            notes.append(f'Judge stability std across runs: {judge_std}')
        notes.append('LCSE reporting: lead with groundedness_score (support); authority_multiplier is prestige only; trust_index is secondary.')
        research = build_research_block(evidence_mode=evidence_mode, discovery_weight=origin_weight, groundedness_score=groundedness, authority_multiplier=round(mean_authority, 2), trust_index=trust_index, caller_url_count=n_caller, discovered_url_count=n_discovered)
        return EvaluateResponse(groundedness_score=groundedness, authority_multiplier=round(mean_authority, 2), trust_index=trust_index, analyst_reasoning=reasoning, per_url_authority=per_url, evidence=evidence_items, evidence_quality=quality, evidence_mode=evidence_mode, discovery_weight=origin_weight, discovered_urls=discovered_items, judge_std=judge_std, model_used=model_name, claim_count=claim_count, notes=notes, research=research)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Evaluation pipeline failed: {exc}') from exc
