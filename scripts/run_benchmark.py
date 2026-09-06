from __future__ import annotations
import json
import time
from pathlib import Path
import pandas as pd
import requests
ROOT = Path(__file__).resolve().parent.parent
API_URL = 'http://127.0.0.1:8000/v1/evaluate'
HEALTH_URL = 'http://127.0.0.1:8000/health'
OLLAMA_GENERATE_URL = 'http://127.0.0.1:11434/api/generate'
DATASET_PATH = ROOT / 'data' / 'evaluation_dataset.json'
RESULTS_DIR = ROOT / 'results'
METRICS_CSV = RESULTS_DIR / 'benchmark_metrics.csv'
TARGET_MODELS = ['llama3.1', 'phi3']
EVAL_SAMPLE_SIZE = 50

def warmup_model(model_name: str) -> None:
    print(f"[benchmark] warming up model '{model_name}'")
    try:
        requests.post(OLLAMA_GENERATE_URL, json={'model': model_name, 'prompt': 'warmup', 'stream': False}, timeout=120)
    except Exception as exc:
        print(f'[benchmark] warmup failed: {exc}')

def run_benchmark() -> None:
    try:
        health = requests.get(HEALTH_URL, timeout=5)
        print(f'[benchmark] api health: {health.json()}')
    except Exception as exc:
        print(f'[benchmark] API not reachable at {HEALTH_URL}: {exc}')
        print('            start with: python -m linkground')
        return
    if not DATASET_PATH.exists():
        print(f'[benchmark] missing dataset: {DATASET_PATH}')
        print('            generate with: python scripts/build_dataset.py')
        return
    with open(DATASET_PATH, 'r', encoding='utf-8') as handle:
        cases = json.load(handle)
    sample = cases[:EVAL_SAMPLE_SIZE]
    records: list[dict] = []
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for model_name in TARGET_MODELS:
        print(f'\n[benchmark] model={model_name} n={len(sample)}')
        print('=' * 72)
        warmup_model(model_name)
        for index, case in enumerate(sample, start=1):
            payload = {'urls': case['urls'], 'statement': case['statement'], 'model': model_name, 'judge_runs': 1}
            started = time.time()
            try:
                response = requests.post(API_URL, json=payload, timeout=180)
                latency = time.time() - started
                if response.status_code != 200:
                    print(f'[benchmark] HTTP {response.status_code} on case {index}: {response.text[:200]}')
                    continue
                body = response.json()
                reasoning = (body.get('analyst_reasoning') or '').replace('\n', ' | ')
                records.append({'model': model_name, 'statement': case['statement'], 'expected_score': case['expected_score'], 'groundedness_score': body.get('groundedness_score', 0.0), 'authority_multiplier': body.get('authority_multiplier', 1.0), 'trust_index': body.get('trust_index', 0.0), 'evidence_quality': body.get('evidence_quality'), 'judge_std': body.get('judge_std'), 'latency_seconds': round(latency, 2), 'analyst_reasoning': reasoning[:2000], 'per_url_authority': json.dumps(body.get('per_url_authority', []))})
                pd.DataFrame(records).to_csv(METRICS_CSV, index=False)
                print(f"[benchmark] {model_name} {index}/{len(sample)} ground={body.get('groundedness_score')} (primary) trust={body.get('trust_index')} eq={body.get('evidence_quality')} expected={case['expected_score']} latency={latency:.2f}s")
            except Exception as exc:
                print(f'[benchmark] case {index} failed: {exc}')
    pd.DataFrame(records).to_csv(METRICS_CSV, index=False)
    print(f'\n[benchmark] wrote {METRICS_CSV}')
if __name__ == '__main__':
    run_benchmark()
