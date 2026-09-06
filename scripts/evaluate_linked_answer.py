from __future__ import annotations
import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import requests
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API = 'http://127.0.0.1:8000/v1/evaluate'
DEFAULT_HEALTH = 'http://127.0.0.1:8000/health'
DEFAULT_OLLAMA = 'http://127.0.0.1:11434/api/chat'
URL_RE = re.compile('https?://[^\\s\\]\\)\\"\'<>]+', re.IGNORECASE)
STOPWORDS = {'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'for', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'as', 'at', 'from', 'that', 'this', 'it', 'its', 'into', 'about', 'site', 'website', 'page', 'https', 'http', 'www', 'com', 'org', 'net', 'best', 'most', 'very', 'also', 'using', 'used'}
GENERIC_MATCH_TOKENS = frozenset({'site', 'sites', 'place', 'places', 'historic', 'historical', 'history', 'heritage', 'foundation', 'foundations', 'guide', 'closer', 'look', 'means', 'ideology', 'accuracy', 'when', 'listed', 'regarded', 'widely', 'top', 'best', 'most', 'world', 'global', 'travel', 'traveler', 'travelers', 'rating', 'ratings', 'rank', 'ranked', 'ranking', 'rankings', 'list', 'lists', 'blog', 'article', 'report', 'reports', 'study', 'studies', 'market', 'inside', 'about', 'en', 'blog', 'must', 'see', 'visited', 'visitor', 'visitors', 'loved', 'complained', 'landmarks', 'monument', 'monuments', 'ancient', 'significant', 'significance', 'objective', 'sense', 'single', 'universally', 'accepted', 'different', 'organizations', 'publish', 'methodology', 'biases', 'bias', 'biased', 'consumer', 'politics', 'capacity', 'emotional', 'impact', 'satisfaction', 'measure', 'not', 'less', 'still', 'shaped', 'especially', 'some', 'guides', 'present', 'interpretive', 'ideological', 'accuracy', 'value', 'values', 'having', 'does', 'designates', 'outstanding', 'universal'})
CLAIM_URL_HINTS: list[tuple[re.Pattern[str], tuple[str, ...]]] = [(re.compile('\\bunesco\\b|outstanding universal value|world heritage', re.IGNORECASE), ('unesco.org', 'whc.unesco', 'thecollector.com', 'ancient-monuments')), (re.compile("\\btripadvisor\\b|travelers'? choice|vacationstravel", re.IGNORECASE), ('tripadvisor.', 'vacationstravel.com', 'tripadvisor.mediaroom')), (re.compile('most loved|sentiment|holafly|emotional (?:impact|resonance)', re.IGNORECASE), ('holafly.com', 'most-loved-and-complained', 'esim.holafly')), (re.compile('heritage foundation|ideological bias|engagingplaces|narrative framing', re.IGNORECASE), ('engagingplaces.net', 'heritage-foundation')), (re.compile('most visited|visitor count|forbidden city|sapiro', re.IGNORECASE), ('sapiro.app', 'most-visited-monuments')), (re.compile('pyramids?|giza|angkor|machu\\s*picchu|petra|acropolis|colosseum|taj mahal|great wall|mesopotam', re.IGNORECASE), ('thecollector.com', 'ancient-monuments', 'unesco.org', 'britannica.com'))]

def _tokenize(text: str) -> set[str]:
    raw = re.findall('[a-z0-9]+', (text or '').lower())
    return {tok for tok in raw if len(tok) >= 3 and tok not in STOPWORDS}

def _specific_tokens(tokens: set[str]) -> set[str]:
    return {tok for tok in tokens if tok not in GENERIC_MATCH_TOKENS and len(tok) >= 4}

def url_match_tokens(url: str) -> set[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix('www.')
    host_parts = re.split('[.\\-]+', host)
    path_parts = re.split('[/\\-_]+', parsed.path.lower())
    return _tokenize(' '.join(host_parts + path_parts))

def claim_url_overlap(statement: str, url: str, *, specific_only: bool=False) -> float:
    claim_tokens = _tokenize(statement)
    url_tokens = url_match_tokens(url)
    if specific_only:
        claim_tokens = _specific_tokens(claim_tokens)
        url_tokens = _specific_tokens(url_tokens)
    if not claim_tokens or not url_tokens:
        return 0.0
    return len(claim_tokens & url_tokens) / len(claim_tokens)

def _hint_score(statement: str, url: str) -> float:
    hay = url.lower()
    score = 0.0
    for pattern, needles in CLAIM_URL_HINTS:
        if not pattern.search(statement or ''):
            continue
        if any((needle in hay for needle in needles)):
            score += 1.0
    return score

def _match_score(statement: str, url: str) -> float:
    specific = claim_url_overlap(statement, url, specific_only=True)
    generic = claim_url_overlap(statement, url, specific_only=False)
    hint = _hint_score(statement, url)
    return 3.0 * specific + 0.15 * generic + 1.25 * hint

def validate_and_reassign_urls(statement: str, assigned: list[str], url_pool: list[str], min_overlap: float=0.08) -> tuple[list[str], str]:
    if not url_pool:
        return (assigned, 'empty_pool')
    scored_assigned = [(_match_score(statement, url), url) for url in assigned]
    best_assigned = max((score for score, _ in scored_assigned), default=0.0)
    pool_scored = sorted(((_match_score(statement, url), url) for url in url_pool), key=lambda item: item[0], reverse=True)
    best_pool_score, best_pool_url = pool_scored[0]
    specific_assigned = max((claim_url_overlap(statement, url, specific_only=True) for url in assigned), default=0.0)
    specific_best = claim_url_overlap(statement, best_pool_url, specific_only=True)
    hint_best = _hint_score(statement, best_pool_url)
    hint_assigned = max((_hint_score(statement, url) for url in assigned), default=0.0)
    keep_llm = False
    if assigned:
        if best_assigned + 1e-09 >= best_pool_score:
            keep_llm = True
        elif hint_assigned > 0 and hint_assigned >= hint_best:
            keep_llm = True
        elif specific_best <= specific_assigned + 1e-09 and hint_best <= hint_assigned:
            keep_llm = True
        elif best_pool_score < 0.35 and hint_best == 0 and (specific_best < min_overlap):
            keep_llm = True
    if keep_llm and assigned:
        note = 'llm_ok'
        if best_pool_score > best_assigned and (specific_best <= specific_assigned or hint_best == 0):
            note = 'llm_kept_reject_generic_reassign'
        return (assigned[:2], note)
    if best_pool_score >= 0.35 or specific_best >= min_overlap or hint_best > 0:
        chosen = [url for score, url in pool_scored if score >= 0.35 or _hint_score(statement, url) > 0][:2]
        if not chosen:
            chosen = [best_pool_url]
        note = 'reassigned_overlap'
        if assigned and assigned[0] != chosen[0]:
            note = f'reassigned_overlap (was {assigned[0]})'
        return (chosen, note)
    if assigned:
        return (assigned[:2], 'low_overlap_kept_llm')
    return ([url_pool[0]], 'fallback_first_url')

def normalize_url(url: str) -> str:
    cleaned = url.strip().rstrip('.,);]')
    parsed = urlparse(cleaned)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError(f'Invalid URL: {url}')
    return cleaned

def extract_urls_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.findall(text or ''):
        try:
            url = normalize_url(match)
        except ValueError:
            continue
        if url not in seen:
            seen.add(url)
            found.append(url)
    return found

def load_url_pool(answer_text: str, urls: list[str] | None, urls_file: Path | None) -> list[str]:
    pool: list[str] = []
    seen: set[str] = set()

    def add_many(items: list[str]) -> None:
        for item in items:
            try:
                url = normalize_url(item)
            except ValueError:
                continue
            if url not in seen:
                seen.add(url)
                pool.append(url)
    add_many(extract_urls_from_text(answer_text))
    if urls:
        add_many(urls)
    if urls_file:
        lines = [line.strip() for line in urls_file.read_text(encoding='utf-8').splitlines() if line.strip() and (not line.strip().startswith('#'))]
        add_many(lines)
    return pool

def ollama_chat(model: str, system: str, user: str, ollama_url: str) -> str:
    payload = {'model': model, 'stream': False, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], 'options': {'temperature': 0.0, 'num_predict': 1200}}
    response = requests.post(ollama_url, json=payload, timeout=180)
    response.raise_for_status()
    body = response.json()
    message = body.get('message')
    if isinstance(message, dict):
        return message.get('content', '') or ''
    return body.get('response', '') or ''

def extract_json_payload(text: str) -> Any:
    text = (text or '').strip()
    if not text:
        raise ValueError('Empty model response')
    fence = re.search('```(?:json)?\\s*(\\{.*?\\}|\\[.*?\\])\\s*```', text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return json.loads(fence.group(1))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start_obj, end_obj = (text.find('{'), text.rfind('}'))
    if start_obj != -1 and end_obj > start_obj:
        return json.loads(text[start_obj:end_obj + 1])
    start_arr, end_arr = (text.find('['), text.rfind(']'))
    if start_arr != -1 and end_arr > start_arr:
        return json.loads(text[start_arr:end_arr + 1])
    raise ValueError(f'Could not parse JSON from model output: {text[:300]!r}')

def propose_missing_urls(answer_text: str, model: str, ollama_url: str) -> list[str]:
    system = 'You extract website names from text and propose their most likely official or gallery URLs. Return JSON only.'
    user = f"""From the answer below, list named websites, products, or galleries and propose\nthe best public URL for each (official site or well-known awards/gallery page).\n\nReturn ONLY JSON:\n{'entities': [\n    {'name': \"...\", \"url\": \"https://...\"} \n  ]\n} \n\nANSWER:\n{answer_text}\n"""
    raw = ollama_chat(model, system, user, ollama_url)
    data = extract_json_payload(raw)
    entities = data.get('entities', []) if isinstance(data, dict) else data
    urls: list[str] = []
    for item in entities or []:
        if not isinstance(item, dict):
            continue
        url = item.get('url')
        if isinstance(url, str):
            try:
                urls.append(normalize_url(url))
            except ValueError:
                continue
    return urls

def split_and_assign_claims(answer_text: str, url_pool: list[str], model: str, ollama_url: str) -> list[dict[str, Any]]:
    system = 'You are a claim decomposition and evidence-routing engine. Return JSON only. Never chat.'
    numbered_urls = '\n'.join((f'{index}. {url}' for index, url in enumerate(url_pool)))
    user = f"""Split the ANSWER into atomic factual claims.\nAssign each claim to the 1-2 best matching URLs from URL_POOL.\n\nMatching rules:\n- Only use indexes from URL_POOL.\n- Match by entity name in the claim to the URL path/domain\n  (e.g. Casa di Solare -> casa-di-solare URL, RelicVault -> relicvault URL,\n  Awwwards gallery -> awwwards.com/websites/three-js, rankings -> rankings URL).\n- Do NOT assign a claim about site A to a page about site B.\n- Prefer the most specific supporting page over a generic homepage.\n- If unsure, pick the closest gallery/ranking page rather than an unrelated nominee page.\n\nSplit rules:\n- Keep framing / meta claims that affect meaning (e.g. "there is no single best site").\n- Do not over-split relative clauses into separate claims.\n- Prefer fewer, complete factual units over many fragments.\n\nReturn ONLY JSON:\n{'claims': [\n    {'id': \"C01\",\n      \"statement\": \"one atomic claim\",\n      \"url_indexes\": [0]\n    } \n  ]\n} \n\nURL_POOL:\n{numbered_urls}\n\nANSWER:\n{answer_text}\n"""
    raw = ollama_chat(model, system, user, ollama_url)
    data = extract_json_payload(raw)
    claims_raw = data.get('claims', []) if isinstance(data, dict) else data
    claims: list[dict[str, Any]] = []
    for index, item in enumerate(claims_raw or [], start=1):
        if not isinstance(item, dict):
            continue
        statement = str(item.get('statement') or '').strip()
        if not statement:
            continue
        indexes = item.get('url_indexes') or item.get('urls') or []
        assigned: list[str] = []
        for value in indexes:
            if isinstance(value, int) and 0 <= value < len(url_pool):
                assigned.append(url_pool[value])
            elif isinstance(value, str):
                try:
                    candidate = normalize_url(value)
                except ValueError:
                    continue
                if candidate in url_pool:
                    assigned.append(candidate)
        deduped: list[str] = []
        seen: set[str] = set()
        for url in assigned:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        validated, match_note = validate_and_reassign_urls(statement, deduped, url_pool)
        claim_id = str(item.get('id') or f'C{index:02d}')
        claims.append({'id': claim_id, 'statement': statement, 'urls': validated, 'url_match_note': match_note, 'url_overlap': round(max((claim_url_overlap(statement, url, specific_only=True) for url in validated), default=0.0), 3)})
    return claims

def score_claim(api_url: str, statement: str, urls: list[str], model: str, judge_runs: int=1, *, use_discovery: bool=False) -> dict[str, Any]:
    started = time.time()
    if use_discovery:
        payload = {'urls': [], 'statement': statement, 'model': model, 'judge_runs': judge_runs, 'discover_evidence': True, 'discovery_depth': 0, 'max_discovered_urls': 3}
    else:
        payload = {'urls': urls, 'statement': statement, 'model': model, 'judge_runs': judge_runs, 'discover_evidence': False}
    response = requests.post(api_url, json=payload, timeout=180 * max(1, judge_runs))
    latency = round(time.time() - started, 2)
    if response.status_code != 200:
        return {'error': f'HTTP {response.status_code}: {response.text[:300]}', 'latency_seconds': latency}
    body = response.json()
    return {'groundedness_score': body.get('groundedness_score'), 'authority_multiplier': body.get('authority_multiplier'), 'trust_index': body.get('trust_index'), 'evidence_quality': body.get('evidence_quality'), 'evidence_mode': body.get('evidence_mode'), 'discovery_weight': body.get('discovery_weight'), 'discovered_urls': body.get('discovered_urls', []), 'evidence': body.get('evidence', []), 'judge_std': body.get('judge_std'), 'notes': body.get('notes', []), 'per_url_authority': body.get('per_url_authority', []), 'analyst_reasoning': body.get('analyst_reasoning', ''), 'latency_seconds': latency, 'used_discovery': use_discovery}

def claim_needs_discovery(claim: dict[str, Any]) -> bool:
    note = str(claim.get('url_match_note') or '')
    overlap = claim.get('url_overlap')
    if note.startswith('reassigned_overlap'):
        return False
    if note.startswith('llm_kept_reject_generic_reassign'):
        return False
    if note in {'low_overlap_kept_llm', 'fallback_first_url', 'empty_pool'}:
        return True
    if note.startswith('llm_ok'):
        return isinstance(overlap, (int, float)) and overlap < 0.08
    if isinstance(overlap, (int, float)) and overlap < 0.08:
        return True
    if not claim.get('urls'):
        return True
    return False

def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if isinstance(row.get('groundedness_score'), (int, float))]
    if not scored:
        return {'claim_count': len(rows), 'scored_count': 0, 'mean_groundedness': None, 'mean_authority': None, 'mean_trust_index': None}
    caller_rows = [row for row in scored if not row.get('used_discovery')]
    discovered_rows = [row for row in scored if row.get('used_discovery')]
    summary = {'claim_count': len(rows), 'scored_count': len(scored), 'mean_groundedness': round(sum((float(row['groundedness_score']) for row in scored)) / len(scored), 3), 'mean_authority': round(sum((float(row['authority_multiplier']) for row in scored)) / len(scored), 3), 'mean_trust_index': round(sum((float(row['trust_index']) for row in scored)) / len(scored), 3), 'min_groundedness': min((float(row['groundedness_score']) for row in scored)), 'max_groundedness': max((float(row['groundedness_score']) for row in scored)), 'caller_linked_count': len(caller_rows), 'discovery_count': len(discovered_rows)}
    if caller_rows:
        summary['mean_groundedness_caller'] = round(sum((float(row['groundedness_score']) for row in caller_rows)) / len(caller_rows), 3)
    if discovered_rows:
        summary['mean_groundedness_discovered'] = round(sum((float(row['groundedness_score']) for row in discovered_rows)) / len(discovered_rows), 3)
    return summary

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Auto-split an LLM answer into claim→link pairs and evaluate via LinkGround.')
    parser.add_argument('--answer-file', type=Path, required=True, help='Path to the LLM answer text')
    parser.add_argument('--urls-file', type=Path, default=None, help='Optional newline-separated URL pool')
    parser.add_argument('--url', action='append', default=[], help='Add a URL to the evidence pool')
    parser.add_argument('--propose-urls', action='store_true', help='If the answer lacks URLs, ask Ollama to propose candidate URLs for named sites')
    parser.add_argument('--model', default='llama3.1', help='Ollama model for split/assign + LinkGround analyst')
    parser.add_argument('--judge-runs', type=int, default=1, help='Repeat analyst scoring per claim for stability (passed to API)')
    parser.add_argument('--api-url', default=DEFAULT_API)
    parser.add_argument('--health-url', default=DEFAULT_HEALTH)
    parser.add_argument('--ollama-url', default=DEFAULT_OLLAMA)
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'linked_answer_eval.json', help='Where to write the JSON report')
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    answer_text = args.answer_file.read_text(encoding='utf-8').strip()
    if not answer_text:
        raise SystemExit('Answer file is empty.')
    try:
        health = requests.get(args.health_url, timeout=5)
        print(f'[linked-eval] API health: {health.json()}')
    except Exception as exc:
        raise SystemExit(f'LinkGround API not reachable at {args.health_url}: {exc}') from exc
    url_pool = load_url_pool(answer_text, args.url, args.urls_file)
    if args.propose_urls or not url_pool:
        print('[linked-eval] proposing candidate URLs from named entities...')
        proposed = propose_missing_urls(answer_text, args.model, args.ollama_url)
        for url in proposed:
            if url not in url_pool:
                url_pool.append(url)
    if not url_pool:
        raise SystemExit('No URLs available. Pass --urls-file / --url, embed links in the answer, or use --propose-urls.')
    print(f'[linked-eval] URL pool size: {len(url_pool)}')
    for index, url in enumerate(url_pool):
        print(f'  [{index}] {url}')
    print('[linked-eval] splitting answer into claims and assigning URLs...')
    claims = split_and_assign_claims(answer_text, url_pool, args.model, args.ollama_url)
    if not claims:
        raise SystemExit('Model returned no claims.')
    print(f'[linked-eval] claims: {len(claims)}')
    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claims, start=1):
        print(f"\n[linked-eval] {claim['id']} ({index}/{len(claims)})")
        print(f"  statement: {claim['statement'][:120]}")
        print(f"  urls: {claim['urls']} ({claim.get('url_match_note')})")
        use_discovery = claim_needs_discovery(claim)
        if use_discovery:
            print('  evidence: DISCOVERY (discounted weight; no reliable caller link)')
        scored = score_claim(args.api_url, claim['statement'], claim['urls'], args.model, judge_runs=args.judge_runs, use_discovery=use_discovery)
        row = {**claim, **scored}
        rows.append(row)
        if 'error' in row:
            print(f"  ERROR: {row['error']}")
        else:
            print(f"  groundedness={row['groundedness_score']} (authority-agnostic) mode={row.get('evidence_mode')} disc_w={row.get('discovery_weight')} authority={row['authority_multiplier']} trust={row['trust_index']} evidence_q={row.get('evidence_quality')} latency={row['latency_seconds']}s")
    summary = aggregate(rows)
    report = {'answer_file': str(args.answer_file), 'model': args.model, 'judge_runs': args.judge_runs, 'url_pool': url_pool, 'caveats': ['mean_groundedness is the primary authority-agnostic result.', 'Caller-linked claims use full weight; discovery-backed claims use discovery_weight < 1.', 'mean_trust_index mixes Open PageRank popularity with support; do not treat as pure truth.', 'Ternary F1 from other scripts is secondary; prefer MAE/RMSE on continuous scores.', 'Claim→URL pairs include url_match_note after token-overlap validation.'], 'summary': summary, 'claims': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('\n' + '=' * 72)
    print('AUTOMATED CLAIM->LINK EVALUATION SUMMARY')
    print('=' * 72)
    print(json.dumps(summary, indent=2))
    print(f'\nWrote {args.output}')
if __name__ == '__main__':
    main()
