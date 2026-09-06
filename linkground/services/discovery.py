from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse
import httpx
from bs4 import BeautifulSoup
from linkground.config import DISCOVERY_DEPTH, DISCOVERY_MAX_PAGES, DISCOVERY_MAX_URLS, WIKIPEDIA_API_URL
from linkground.services.trusted_sources import is_trusted_url
STOPWORDS = frozenset({'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'as', 'at', 'from', 'that', 'this', 'it', 'its', 'into', 'about', 'than', 'more', 'most', 'very', 'also', 'not', 'no', 'yes', 'can', 'may', 'will', 'would', 'could', 'should', 'have', 'has', 'had', 'been', 'their', 'there', 'these', 'those', 'which', 'who', 'what', 'when', 'where', 'how', 'why', 'best', 'rated', 'rating', 'site'})
USER_AGENT = 'LinkGround/2.4 (UROP research tool; local eval; contact: local-dev@linkground.invalid)'

@dataclass
class DiscoveredUrl:
    url: str
    score: float
    origin: str
    title: str = ''

def _tokenize(text: str) -> set[str]:
    tokens = re.findall('[a-z0-9]+', (text or '').lower())
    return {t for t in tokens if len(t) >= 3 and t not in STOPWORDS}

def _overlap(claim_tokens: set[str], text: str) -> float:
    page_tokens = _tokenize(text)
    if not claim_tokens or not page_tokens:
        return 0.0
    return len(claim_tokens & page_tokens) / len(claim_tokens)

def _canonicalize(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None
    clean = urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/') or '/', '', '', ''))
    if not is_trusted_url(clean):
        return None
    return clean

async def _wikipedia_search(statement: str, limit: int=5) -> list[DiscoveredUrl]:
    claim_tokens = _tokenize(statement)
    ordered = []
    seen: set[str] = set()
    for tok in re.findall('[a-z0-9]+', (statement or '').lower()):
        if tok in claim_tokens and tok not in seen:
            seen.add(tok)
            ordered.append(tok)
        if len(ordered) >= 10:
            break
    query = ' '.join(ordered) or (statement or '')[:80]
    params = {'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': limit, 'format': 'json', 'utf8': 1}
    headers = {'User-Agent': USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        response = await client.get(WIKIPEDIA_API_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
    results: list[DiscoveredUrl] = []
    for hit in data.get('query', {}).get('search', []) or []:
        title = str(hit.get('title') or '').strip()
        if not title:
            continue
        slug = title.replace(' ', '_')
        url = f'https://en.wikipedia.org/wiki/{slug}'
        snippet = BeautifulSoup(str(hit.get('snippet') or ''), 'html.parser').get_text(' ')
        score = _overlap(claim_tokens, f'{title} {snippet}')
        results.append(DiscoveredUrl(url=url, score=max(score, 0.15), origin='wikipedia_search', title=title))
    if not results and ordered:
        short_query = ' '.join(ordered[:4])
        params['srsearch'] = short_query
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            response = await client.get(WIKIPEDIA_API_URL, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
        for hit in data.get('query', {}).get('search', []) or []:
            title = str(hit.get('title') or '').strip()
            if not title:
                continue
            slug = title.replace(' ', '_')
            url = f'https://en.wikipedia.org/wiki/{slug}'
            snippet = BeautifulSoup(str(hit.get('snippet') or ''), 'html.parser').get_text(' ')
            score = _overlap(claim_tokens, f'{title} {snippet}')
            results.append(DiscoveredUrl(url=url, score=max(score, 0.15), origin='wikipedia_search', title=title))
    return results

async def _fetch_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url, timeout=25.0)
        if response.status_code != 200:
            return None
        ctype = response.headers.get('content-type', '')
        if 'html' not in ctype and 'text' not in ctype:
            return None
        return response.text
    except Exception:
        return None

def _extract_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    found: list[str] = []
    for anchor in soup.find_all('a', href=True):
        href = anchor.get('href')
        if not href or href.startswith('#'):
            continue
        absolute = urljoin(base_url, href)
        canonical = _canonicalize(absolute)
        if canonical:
            found.append(canonical)
    return found

def _page_relevance(claim_tokens: set[str], html: str, url: str) -> float:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    text = soup.get_text(' ', strip=True)[:8000]
    return _overlap(claim_tokens, f'{url} {title} {text}')

async def _bfs_expand(seeds: Iterable[str], statement: str, depth: int, max_pages: int) -> list[DiscoveredUrl]:
    claim_tokens = _tokenize(statement)
    queue: list[tuple[str, int, str]] = [(url, 0, 'seed') for url in seeds]
    seen: set[str] = set()
    ranked: list[DiscoveredUrl] = []
    headers = {'User-Agent': USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        while queue and len(seen) < max_pages:
            url, level, origin = queue.pop(0)
            canonical = _canonicalize(url)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            html = await _fetch_html(client, canonical)
            if not html:
                continue
            score = _page_relevance(claim_tokens, html, canonical)
            if score >= 0.08 or origin == 'wikipedia_search':
                ranked.append(DiscoveredUrl(url=canonical, score=score, origin=origin if level == 0 else 'bfs'))
            if level >= depth:
                continue
            for link in _extract_links(canonical, html)[:20]:
                if link not in seen:
                    queue.append((link, level + 1, 'bfs'))
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked

async def discover_evidence_urls(statement: str, *, max_urls: int | None=None, depth: int | None=None, max_pages: int | None=None) -> list[DiscoveredUrl]:
    limit = max_urls if max_urls is not None else DISCOVERY_MAX_URLS
    crawl_depth = depth if depth is not None else DISCOVERY_DEPTH
    page_budget = max_pages if max_pages is not None else DISCOVERY_MAX_PAGES
    wiki_hits = await _wikipedia_search(statement, limit=max(5, limit))
    seed_urls = [hit.url for hit in wiki_hits]
    expanded = await _bfs_expand(seeds=seed_urls, statement=statement, depth=max(0, crawl_depth), max_pages=page_budget)
    by_url: dict[str, DiscoveredUrl] = {}
    for item in [*wiki_hits, *expanded]:
        prior = by_url.get(item.url)
        if prior is None:
            by_url[item.url] = item
            continue
        keep_title = prior.title or item.title
        keep_origin = prior.origin if prior.origin == 'wikipedia_search' else item.origin
        if item.score > prior.score:
            by_url[item.url] = DiscoveredUrl(url=item.url, score=item.score, origin=keep_origin if keep_origin == 'wikipedia_search' else item.origin, title=keep_title)
        else:
            by_url[item.url] = DiscoveredUrl(url=prior.url, score=prior.score, origin=keep_origin, title=keep_title)
    merged = sorted(by_url.values(), key=lambda item: item.score, reverse=True)
    filtered = [item for item in merged if item.score >= 0.1]
    chosen = filtered[:limit] if filtered else merged[:limit]
    return chosen
