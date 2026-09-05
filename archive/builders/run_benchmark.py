import time
import json
from pathlib import Path

import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
API_URL = "http://localhost:8000/v2/evaluate-provenance"
HEALTH_URL = "http://localhost:8000/health"
OLLAMA_MODEL_URL = "http://localhost:11434/api/generate"
RESULTS_DIR = ROOT / "results"
DATASET_PATH = ROOT / "data" / "research_dataset.json"
METRICS_CSV = RESULTS_DIR / "hardware_vs_accuracy_metrics.csv"

# Cross-model comparison on your local Ollama runtime
target_models = ["llama3.1", "phi3"]
EVAL_N = 50


def set_active_ollama_model(model_name: str):
    print(f"🧠 Loading and warming up local model: '{model_name}'...")
    try:
        requests.post(
            OLLAMA_MODEL_URL,
            json={"model": model_name, "prompt": "warmup", "stream": False},
            timeout=120,
        )
    except Exception as e:
        print(f"⚠️ Warmup signal dropped: {e}")


def execute_hardware_tradeoff_benchmark():
    try:
        health = requests.get(HEALTH_URL, timeout=5)
        print(f"🩺 API health: {health.json()}")
    except Exception as e:
        print(f"❌ API not reachable at {HEALTH_URL}: {e}")
        print("   Start it with: python src/advanced_main_v2.py")
        return

    try:
        with open(DATASET_PATH, "r", encoding="utf-8") as f:
            test_cases = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: '{DATASET_PATH}' missing! Run builders/data_builder.py first.")
        return

    evaluation_slice = test_cases[:EVAL_N]
    all_model_records = []
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for model in target_models:
        print(f"\n🚀 STARTING BENCHMARK FOR MODEL: {model.upper()} (N={len(evaluation_slice)})")
        print("=" * 80)
        set_active_ollama_model(model)

        for i, case in enumerate(evaluation_slice):
            payload = {
                "urls": case["urls"],
                "llm_output_to_test": case["statement"],
                "model": model,
            }

            start_time = time.time()
            try:
                res = requests.post(API_URL, json=payload, timeout=180)
                elapsed = time.time() - start_time

                if res.status_code == 200:
                    out = res.json()
                    reasoning = (out.get("academic_reasoning") or "").replace("\n", " | ")
                    all_model_records.append({
                        "Model_Engine": model,
                        "Statement": case["statement"],
                        "Actual_Truth": case["expected_score"],
                        "Predicted_Truth": out.get("groundedness_score", 0.0),
                        "Authority_Multiplier": out.get("source_authority_multiplier", 1.0),
                        "Final_Trust_Index": out.get("final_verified_trust_index", 0.0),
                        "Latency_Seconds": round(elapsed, 2),
                        "Academic_Reasoning": reasoning[:2000],
                        "Per_URL_Authority": json.dumps(out.get("per_url_authority", [])),
                    })
                    # Flush progressively so a crash still leaves partial results
                    pd.DataFrame(all_model_records).to_csv(METRICS_CSV, index=False)
                    print(
                        f"✨ [{model}] Case {i+1}/{len(evaluation_slice)} | "
                        f"ground={out.get('groundedness_score')} "
                        f"trust={out.get('final_verified_trust_index')} "
                        f"actual={case['expected_score']} | "
                        f"Latency: {elapsed:.2f}s"
                    )
                else:
                    print(f"❌ Server Error code {res.status_code} on entry {i}: {res.text[:200]}")
            except Exception as e:
                print(f"❌ Pipeline interruption on case {i}: {e}")

    df = pd.DataFrame(all_model_records)
    df.to_csv(METRICS_CSV, index=False)
    print(f"\n💾 System trade-off data written to '{METRICS_CSV}'")
    print("   Columns include Predicted_Truth (groundedness), Final_Trust_Index, and Academic_Reasoning.")


if __name__ == "__main__":
    execute_hardware_tradeoff_benchmark()
