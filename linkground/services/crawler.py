from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse
from crawl4ai import AsyncWebCrawler
from linkground.services import cache as cache_store
from linkground.services.evidence import fallback_text_for_url
_memory_pages: dict[str, tuple[str, str]] = {}

@dataclass
class EvidenceDocument:
    url: str
    text: str
    source: str
    char_count: int

def context_char_budget(url: str) -> int:
    host = urlparse(url).netloc.lower()
    if 'wikipedia.org' in host or 'britannica.com' in host:
        return 6000
    if host.endswith(('.gov', '.edu', '.mil')):
        return 4000
    return 3000

async def _fetch_page(crawler: AsyncWebCrawler, url: str) -> EvidenceDocument:
    if url in _memory_pages:
        text, source = _memory_pages[url]
        return EvidenceDocument(url=url, text=text, source=source, char_count=len(text))
    cached = cache_store.read_crawl_cache(url)
    if cached is not None and (not cached.startswith('[LINKGROUND_FALLBACK]')):
        _memory_pages[url] = (cached, 'cache')
        return EvidenceDocument(url=url, text=cached, source='cache', char_count=len(cached))
    result = await crawler.arun(url=url)
    if result and result.markdown and (len(result.markdown.strip()) > 120):
        text = result.markdown[:context_char_budget(url)]
        source = 'live'
    else:
        text = '[LINKGROUND_FALLBACK]\n' + fallback_text_for_url(url)
        source = 'fallback'
    if source == 'live':
        cache_store.write_crawl_cache(url, text)
    _memory_pages[url] = (text, source)
    return EvidenceDocument(url=url, text=text, source=source, char_count=len(text))

async def collect_evidence(urls: List[str]) -> list[EvidenceDocument]:
    async with AsyncWebCrawler(verbose=False) as crawler:
        return list(await asyncio.gather(*[_fetch_page(crawler, url) for url in urls]))

def format_evidence_block(documents: list[EvidenceDocument], origin_by_url: dict[str, str] | None=None) -> str:
    blocks: list[str] = []
    for index, doc in enumerate(documents, start=1):
        origin = (origin_by_url or {}).get(doc.url, 'caller')
        weight_tag = 'CALLER_FULL_WEIGHT' if origin == 'caller' else 'DISCOVERED_REDUCED_WEIGHT'
        blocks.append(f'\n[SOURCE DOCUMENT {index} | URL: {doc.url} | EVIDENCE_SOURCE: {doc.source} | ORIGIN: {origin} | WEIGHT: {weight_tag}]\n{doc.text}\n')
    return ''.join(blocks)

async def aggregate_source_context(urls: List[str]) -> str:
    documents = await collect_evidence(urls)
    return format_evidence_block(documents)
