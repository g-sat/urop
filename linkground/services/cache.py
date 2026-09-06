from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Dict
from linkground.config import CACHE_TTL_SECONDS, CRAWL_CACHE_DIR, OPR_CACHE_PATH

def ensure_cache_dirs() -> None:
    OPR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRAWL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def load_opr_cache() -> Dict[str, float]:
    ensure_cache_dirs()
    if not OPR_CACHE_PATH.exists():
        return {}
    try:
        with open(OPR_CACHE_PATH, 'r', encoding='utf-8') as handle:
            raw = json.load(handle)
        return {str(key).lower(): float(value) for key, value in raw.items()}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {}

def save_opr_cache(cache: Dict[str, float]) -> None:
    ensure_cache_dirs()
    with open(OPR_CACHE_PATH, 'w', encoding='utf-8') as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)

def crawl_cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode('utf-8')).hexdigest()
    return CRAWL_CACHE_DIR / f'{digest}.txt'

def read_crawl_cache(url: str, ttl_seconds: int | None=None) -> str | None:
    path = crawl_cache_path(url)
    if not path.exists():
        return None
    ttl = CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    age = time.time() - path.stat().st_mtime
    if age > ttl:
        return None
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return None

def write_crawl_cache(url: str, text: str) -> None:
    ensure_cache_dirs()
    crawl_cache_path(url).write_text(text, encoding='utf-8')
