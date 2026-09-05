"""Web crawling with cache and evidence fallbacks."""

from __future__ import annotations

import asyncio
from typing import List
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler

from linkground.services import cache as cache_store
from linkground.services.evidence import fallback_text_for_url

_memory_pages: dict[str, str] = {}


def context_char_budget(url: str) -> int:
    host = urlparse(url).netloc.lower()
    if "wikipedia.org" in host or "britannica.com" in host:
        return 6000
    if host.endswith((".gov", ".edu", ".mil")):
        return 4000
    return 3000


async def _fetch_page_text(crawler: AsyncWebCrawler, url: str) -> str:
    if url in _memory_pages:
        return _memory_pages[url]

    cached = cache_store.read_crawl_cache(url)
    if cached is not None:
        _memory_pages[url] = cached
        return cached

    result = await crawler.arun(url=url)
    if result and result.markdown and len(result.markdown.strip()) > 120:
        text = result.markdown[: context_char_budget(url)]
    else:
        print(f"[crawler] weak/empty crawl for {url}; using evidence fallback")
        text = fallback_text_for_url(url)

    cache_store.write_crawl_cache(url, text)
    _memory_pages[url] = text
    return text


async def aggregate_source_context(urls: List[str]) -> str:
    """Crawl all URLs in parallel and return a labeled evidence block."""
    async with AsyncWebCrawler(verbose=False) as crawler:
        pages = await asyncio.gather(*[_fetch_page_text(crawler, url) for url in urls])

    blocks: list[str] = []
    for index, (url, text) in enumerate(zip(urls, pages), start=1):
        blocks.append(f"\n[SOURCE DOCUMENT {index} | URL: {url}]\n{text}\n")
    return "".join(blocks)
