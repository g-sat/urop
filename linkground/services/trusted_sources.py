from __future__ import annotations
from urllib.parse import urlparse
TRUSTED_DOMAINS: frozenset[str] = frozenset({'en.wikipedia.org', 'wikipedia.org', 'www.britannica.com', 'britannica.com', 'www.unesco.org', 'unesco.org', 'whc.unesco.org', 'www.nasa.gov', 'nasa.gov', 'www.nih.gov', 'nih.gov', 'www.cdc.gov', 'cdc.gov', 'www.who.int', 'who.int', 'www.nature.com', 'nature.com', 'www.science.org', 'science.org', 'arxiv.org', 'www.britannica.com', 'www.loc.gov', 'loc.gov', 'www.nationalgeographic.com', 'nationalgeographic.com', 'www.metmuseum.org', 'metmuseum.org', 'www.si.edu', 'si.edu', 'www.bbc.com', 'bbc.com', 'www.bbc.co.uk', 'bbc.co.uk', 'reuters.com', 'www.reuters.com', 'apnews.com', 'www.apnews.com', 'edu', 'gov'})
TRUSTED_SEED_URLS: tuple[str, ...] = ('https://en.wikipedia.org/wiki/Main_Page', 'https://whc.unesco.org/en/list/', 'https://www.britannica.com/')

def normalize_host(url_or_host: str) -> str:
    raw = (url_or_host or '').strip().lower()
    if '://' in raw:
        host = urlparse(raw).netloc
    else:
        host = raw
    return host.removeprefix('www.')

def is_trusted_url(url: str) -> bool:
    host = normalize_host(url)
    if not host:
        return False
    if host in TRUSTED_DOMAINS or f'www.{host}' in TRUSTED_DOMAINS:
        return True
    labels = host.split('.')
    if len(labels) >= 2 and labels[-1] in {'edu', 'gov'}:
        return True
    if len(labels) >= 3 and labels[-2] in {'edu', 'gov', 'ac'}:
        return True
    if host.endswith('.wikipedia.org'):
        return True
    return False
