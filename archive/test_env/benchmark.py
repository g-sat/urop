import time
import json
import requests
import pandas as pd

API_URL = "http://localhost:8000/v1/evaluate"

# 1. Define a research test dataset (Mix of True and False statements)
test_dataset = [
    {
        "url": "https://wikipedia.org",
        "statement": "Wikipedia articles are written by volunteer editors worldwide.",
        "expected": 1.0
    },
    {
        "url": "https://wikipedia.org",
        "statement": "You must pay a monthly subscription fee of $10 to read Wikipedia.",
        "expected": 0.0
    },
    {
        "url": "https://wikipedia.org",
        "statement": "Alan Turing is widely considered to be a foundational figure in artificial intelligence.",
        "expected": 1.0
    },
    {
        "url": "https://wikipedia.org",
        "statement": "The term Artificial Intelligence was first coined in the year 2015 by Google.",
        "expected": 0.0
    }
]

def run_research_benchmark():
    results = []
    print("🚀 Starting Automated UROP Evaluation Benchmark Loop...\n")

    for i, case in enumerate(test_dataset):
        print(f"🔄 Processing Case {i+1}/{len(test_dataset)}...")
        
        payload = {
            "url": case["url"],
            "statement": case["statement"]
        }
        
        # Track processing latency
        start_time = time.time()
        try:
            response = requests.post(API_URL, json=payload)
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                score = data.get("score")
                reason = data.get("reason")
                
                # Check if the local model's judgment matches our expected baseline
                is_correct_judgment = (score == case["expected"])
                
                results.append({
                    "Statement": case["statement"],
                    "Expected Score": case["expected"],
                    "Model Score": score,
                    "Is Judgment Correct": is_correct_judgment,
                    "Latency (seconds)": round(elapsed_time, 2),
                    "Model Reason": reason
                })
                print(f"✅ Completed in {round(elapsed_time, 2)}s. Correct Judgment: {is_correct_judgment}")
            else:
                print(f"❌ Server Error code: {response.status_code}")
        except Exception as e:
            print(f"❌ Connection error during test loop: {e}")

    # 2. Export collected data to a structured CSV for data visualizations
    df = pd.DataFrame(results)
    df.to_csv("evaluation_benchmark_results.csv", index=False)
    print("\n📊 Research Loop Complete! Saved logs to 'evaluation_benchmark_results.csv'")

if __name__ == "__main__":
    # Make sure your server.py is still actively running in another terminal window before running this!
    run_research_benchmark()
