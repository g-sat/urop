from __future__ import annotations
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / '.cache'
OPR_CACHE_PATH = CACHE_DIR / 'opr_domain_ranks.json'
CRAWL_CACHE_DIR = CACHE_DIR / 'crawls'
DATA_DIR = PROJECT_ROOT / 'data'
RESULTS_DIR = PROJECT_ROOT / 'results'
OLLAMA_CHAT_URL = os.getenv('OLLAMA_CHAT_URL', 'http://localhost:11434/api/chat')
OLLAMA_GENERATE_URL = os.getenv('OLLAMA_GENERATE_URL', 'http://localhost:11434/api/generate')
DEFAULT_ANALYST_MODEL = os.getenv('DEFAULT_ANALYST_MODEL', 'llama3.1')
OPR_API_KEY = os.getenv('OPR_API_KEY', '')
OPR_BULK_URL = os.getenv('OPR_BULK_URL', 'https://openpagerank.keywordseverywhere.com/v1/domains/bulk')
API_HOST = os.getenv('API_HOST', '127.0.0.1')
API_PORT = int(os.getenv('API_PORT', '8000'))
AUTHORITY_BASE = 0.8
AUTHORITY_SCALE = 0.5
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', str(7 * 24 * 3600)))
FALLBACK_EVIDENCE_FACTOR = float(os.getenv('FALLBACK_EVIDENCE_FACTOR', '0.6'))
DEFAULT_JUDGE_RUNS = int(os.getenv('DEFAULT_JUDGE_RUNS', '1'))
DISCOVERY_MAX_URLS = int(os.getenv('DISCOVERY_MAX_URLS', '4'))
DISCOVERY_DEPTH = int(os.getenv('DISCOVERY_DEPTH', '1'))
DISCOVERY_MAX_PAGES = int(os.getenv('DISCOVERY_MAX_PAGES', '12'))
WIKIPEDIA_API_URL = os.getenv('WIKIPEDIA_API_URL', 'https://en.wikipedia.org/w/api.php')
DISCOVERY_SCORE_FACTOR = float(os.getenv('DISCOVERY_SCORE_FACTOR', '0.55'))
