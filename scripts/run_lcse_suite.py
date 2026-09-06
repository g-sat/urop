from __future__ import annotations
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
import requests
ROOT = Path(__file__).resolve().parent.parent
LCSE_DIR = ROOT / 'data' / 'lcse'
DEFAULT_API = 'http://127.0.0.1:8000/v1/evaluate'
DEFAULT_HEALTH = 'http://127.0.0.1:8000/health'

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows

def evaluate_case(api_url: str, case: dict[str, Any], model: str) -> dict[str, Any]:
    urls = case.get('urls') or []
    payload: dict[str, Any] = {'statement': case['statement'], 'model': model, 'judge_runs': 1, 'discover_evidence': len(urls) == 0, 'discovery_depth': 0, 'max_discovered_urls': 3}
    if urls:
        payload['urls'] = urls
        payload['discover_evidence'] = False
    started = time.time()
    response = requests.post(api_url, json=payload, timeout=180)
    latency = round(time.time() - started, 2)
    if response.status_code != 200:
        return {**case, 'error': f'HTTP {response.status_code}: {response.text[:300]}', 'latency_seconds': latency}
    body = response.json()
    return {**case, 'groundedness_score': body.get('groundedness_score'), 'authority_multiplier': body.get('authority_multiplier'), 'trust_index': body.get('trust_index'), 'evidence_mode': body.get('evidence_mode'), 'discovery_weight': body.get('discovery_weight'), 'research': body.get('research', {}), 'latency_seconds': latency}

def summarize_spine_a(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if 'error' in row:
            continue
        cells[str(row.get('cell'))].append(row)

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None
    cell_stats = {}
    for cell, items in cells.items():
        supports = [float(r['groundedness_score']) for r in items]
        trusts = [float(r['trust_index']) for r in items]
        inflations = [float((r.get('research') or {}).get('prestige_inflation') or 0.0) for r in items]
        cell_stats[cell] = {'n': len(items), 'mean_support': mean(supports), 'mean_trust': mean(trusts), 'mean_prestige_inflation': mean(inflations)}
    uh = cell_stats.get('UH', {})
    ul = cell_stats.get('UL', {})
    return {'cell_stats': cell_stats, 'prestige_confound_signal': {'uh_mean_trust': uh.get('mean_trust'), 'uh_mean_support': uh.get('mean_support'), 'ul_mean_trust': ul.get('mean_trust'), 'note': 'Spine A expects UH mean_trust >> UH mean_support when prestige inflates unsupported high-prestige pages.'}}

def summarize_spine_b(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if 'error' in row:
            continue
        pairs[str(row.get('pair_id'))][str(row.get('condition'))] = row
    deltas: list[float] = []
    pair_rows = []
    for pair_id, conditions in pairs.items():
        matched = conditions.get('matched')
        swapped = conditions.get('swapped')
        if not matched or not swapped:
            continue
        delta = float(matched['groundedness_score']) - float(swapped['groundedness_score'])
        deltas.append(delta)
        pair_rows.append({'pair_id': pair_id, 'matched_support': matched['groundedness_score'], 'swapped_support': swapped['groundedness_score'], 'delta_swap': round(delta, 3)})
    return {'pairs': pair_rows, 'mean_delta_swap': round(sum(deltas) / len(deltas), 3) if deltas else None, 'note': 'Spine B expects mean_delta_swap > 0 (matched citations score higher than swaps).'}

def summarize_spine_c(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flag_counts: dict[str, int] = defaultdict(int)
    regimes: dict[str, int] = defaultdict(int)
    for row in rows:
        if 'error' in row:
            continue
        regimes[str(row.get('regime') or row.get('evidence_mode'))] += 1
        for flag in (row.get('research') or {}).get('ethics_flags') or []:
            flag_counts[str(flag)] += 1
    return {'regime_counts': dict(regimes), 'ethics_flag_counts': dict(flag_counts), 'note': 'Spine C audits disclosure: discovery/trusted-list flags must appear when caller citations are absent.'}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run LCSE spines A/B/C against LinkGround.')
    parser.add_argument('--spine', choices=['A', 'B', 'C', 'all'], default='all')
    parser.add_argument('--model', default='llama3.1')
    parser.add_argument('--api-url', default=DEFAULT_API)
    parser.add_argument('--health-url', default=DEFAULT_HEALTH)
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'lcse_suite.json')
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    try:
        health = requests.get(args.health_url, timeout=5)
        print('[lcse] health:', health.json())
    except Exception as exc:
        raise SystemExit(f'API not reachable: {exc}') from exc
    catalog = {'A': LCSE_DIR / 'confound_grid.jsonl', 'B': LCSE_DIR / 'citation_swap.jsonl', 'C': LCSE_DIR / 'ethics_audit.jsonl'}
    spines = ['A', 'B', 'C'] if args.spine == 'all' else [args.spine]
    report: dict[str, Any] = {'framework': 'LCSE', 'model': args.model, 'spines_run': spines, 'results': {}, 'summaries': {}}
    for spine in spines:
        path = catalog[spine]
        cases = load_jsonl(path)
        print(f'[lcse] Spine {spine}: {len(cases)} cases from {path.name}')
        rows: list[dict[str, Any]] = []
        for index, case in enumerate(cases, start=1):
            print(f"  [{spine} {index}/{len(cases)}] {case.get('id')}")
            row = evaluate_case(args.api_url, case, args.model)
            rows.append(row)
            if 'error' in row:
                print('    ERROR', row['error'][:120])
            else:
                print(f"    support={row['groundedness_score']} prestige={row['authority_multiplier']} trust={row['trust_index']} mode={row.get('evidence_mode')}")
        report['results'][spine] = rows
        if spine == 'A':
            report['summaries']['A'] = summarize_spine_a(rows)
        elif spine == 'B':
            report['summaries']['B'] = summarize_spine_b(rows)
        else:
            report['summaries']['C'] = summarize_spine_c(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('\n=== LCSE SUMMARY ===')
    print(json.dumps(report['summaries'], indent=2))
    print(f'\nWrote {args.output}')
if __name__ == '__main__':
    main()
