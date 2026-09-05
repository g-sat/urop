import time
import requests
import pandas as pd

API_URL = "http://localhost:8000/v1/evaluate"

# Core research evaluation dataset
research_dataset = [
    {"url": "https://wikipedia.org", "statement": "Wikipedia articles are written by volunteer editors.", "expected": 1.0},
    {"url": "https://wikipedia.org", "statement": "Wikipedia costs $50 per month to access.", "expected": 0.0},
    {"url": "https://wikipedia.org", "statement": "Artificial intelligence research began in the mid-20th century.", "expected": 1.0},
    {"url": "https://wikipedia.org", "statement": "AI was completely invented by Microsoft in 2024.", "expected": 0.0}
]

def execute_benchmark():
    records = []
    print("🚀 Initiating Automated UROP Evaluation Dataset Loop...\n")

    for i, item in enumerate(research_dataset):
        print(f"📋 Running Test Case {i+1}/{len(research_dataset)}...")
        payload = {"url": item["url"], "statement": item["statement"]}
        
        start_time = time.time()
        try:
            res = requests.post(API_URL, json=payload)
            elapsed = time.time() - start_time
            
            if res.status_code == 200:
                out = res.json()
                score = out.get("score")
                correct = (score == item["expected"])
                
                records.append({
                    "Statement": item["statement"],
                    "Expected": item["expected"],
                    "Score": score,
                    "Correct": correct,
                    "Latency": round(elapsed, 2),
                    "Reason": out.get("reason")
                })
                print(f"   📊 Time: {round(elapsed, 2)}s | Accuracy Match: {correct}")
            else:
                print(f"   ❌ Server returned error code: {res.status_code}")
        except Exception as e:
            print(f"   ❌ Connection dropped: {e}")

    df = pd.DataFrame(records)
    df.to_csv("urop_benchmark_metrics.csv", index=False)
    print("\n💾 Data tracking file compiled: 'urop_benchmark_metrics.csv'")

if __name__ == "__main__":
    execute_benchmark()
