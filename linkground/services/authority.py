from __future__ import annotations
from typing import Dict, List
from urllib.parse import urlparse
import httpx
from linkground.config import AUTHORITY_BASE, AUTHORITY_SCALE, OPR_API_KEY, OPR_BULK_URL
from linkground.services import cache as cache_store
_memory_ranks: Dict[str, float] = {}

def normalize_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    if domain.startswith('www.'):
        return domain[4:]
    return domain

def rank_to_multiplier(open_page_rank: float) -> float:
    return AUTHORITY_BASE + float(open_page_rank) / 10.0 * AUTHORITY_SCALE

def _resolve_cached(domain: str, ranks: Dict[str, float]) -> float:
    if domain in ranks:
        return ranks[domain]
    for key, value in ranks.items():
        if domain.endswith(key) or key.endswith(domain):
            return value
    return 1.0

async def fetch_authority_multipliers(urls: List[str]) -> List[float]:
    global _memory_ranks
    if not _memory_ranks:
        _memory_ranks = cache_store.load_opr_cache()
    domains = [normalize_domain(url) for url in urls]
    missing = [domain for domain in domains if domain not in _memory_ranks]
    if missing and OPR_API_KEY:
        headers = {'Authorization': f'Bearer {OPR_API_KEY.strip()}', 'Content-Type': 'application/json'}
        payload = {'domains': missing, 'include_history': False}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(OPR_BULK_URL, json=payload, headers=headers, timeout=8.0)
                if response.status_code == 200:
                    body = response.json()
                    for record in body.get('results', []):
                        name = (record.get('domain') or '').lower()
                        raw_rank = record.get('open_page_rank')
                        if raw_rank is None:
                            _memory_ranks[name] = 1.0
                        else:
                            _memory_ranks[name] = rank_to_multiplier(raw_rank)
                    cache_store.save_opr_cache(_memory_ranks)
            except Exception:
                pass
    return [_resolve_cached(domain, _memory_ranks) for domain in domains]
