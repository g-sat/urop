from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000/v1/evaluate"
HEALTH = "http://127.0.0.1:8000/health"
OLLAMA = "http://127.0.0.1:11434/api/generate"
DATASET = ROOT / "data" / "evaluation_dataset.json"
OUT = ROOT / "results" / "benchmark_metrics.csv"
MODELS = ["llama3.1", "phi3"]
N = 50


def warmup(model: str) -> None:
    try:
        requests.post(OLLAMA, json={"model": model, "prompt": "ok", "stream": False}, timeout=120)
    except Exception:
        pass


def main() -> None:
    try:
        requests.get(HEALTH, timeout=5).raise_for_status()
    except Exception as exc:
        raise SystemExit(f"API down: {exc}") from exc

    if not DATASET.exists():
        raise SystemExit(f"missing {DATASET} — run scripts/build_dataset.py")

    cases = json.loads(DATASET.read_text(encoding="utf-8"))[:N]
    rows: list[dict] = []
    OUT.parent.mkdir(parents=True, exist_ok=True)

    for model in MODELS:
        warmup(model)
        for i, case in enumerate(cases, 1):
            t0 = time.time()
            try:
                resp = requests.post(
                    API,
                    json={
                        "urls": case["urls"],
                        "statement": case["statement"],
                        "model": model,
                        "judge_runs": 1,
                    },
                    timeout=180,
                )
                latency = round(time.time() - t0, 2)
                if resp.status_code != 200:
                    print(f"{model} {i}/{len(cases)} fail {resp.status_code}")
                    continue
                body = resp.json()
                rows.append(
                    {
                        "model": model,
                        "statement": case["statement"],
                        "expected_score": case["expected_score"],
                        "groundedness_score": body.get("groundedness_score", 0.0),
                        "authority_multiplier": body.get("authority_multiplier", 1.0),
                        "trust_index": body.get("trust_index", 0.0),
                        "evidence_quality": body.get("evidence_quality"),
                        "judge_std": body.get("judge_std"),
                        "latency_seconds": latency,
                        "analyst_reasoning": (body.get("analyst_reasoning") or "").replace("\n", " | ")[:2000],
                        "per_url_authority": json.dumps(body.get("per_url_authority", [])),
                    }
                )
                pd.DataFrame(rows).to_csv(OUT, index=False)
                print(
                    f"{model} {i}/{len(cases)}  "
                    f"g={body.get('groundedness_score')}  "
                    f"exp={case['expected_score']}  "
                    f"{latency}s"
                )
            except Exception as exc:
                print(f"{model} {i}/{len(cases)} fail {exc}")

    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
