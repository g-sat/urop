import requests
import json
import time

# Ensure this matches your running server endpoint path route
API_URL = "http://localhost:8000/v2/evaluate-provenance"

scenarios = {
    "1. 100% TRUE CASE (High Authority Sources)": {
        "urls": [
            "https://wikipedia.org",
            "https://wikipedia.org"
        ],
        "llm_output_to_test": "Wikipedia is hosted and managed by a non-profit organization called the Wikimedia Foundation."
    },
    
    "2. 100% FALSE CASE (Blatant Hallucination)": {
        "urls": [
            "https://wikipedia.org"
        ],
        "llm_output_to_test": "Wikipedia was secretly developed by Apple Inc. in 2024 to replace Siri entirely."
    },
    
    "3. PARTIALLY TRUE / PARTIALLY FALSE CASE (Mixed Claims)": {
        "urls": [
            "https://wikipedia.org"  # 👈 DEEP FACTS LINK
        ],
        "llm_output_to_test": "Artificial intelligence research officially began in the mid-20th century, and it was entirely funded and completed by Google in 1956."
    },
    
    "4. HIGH-COMPLEXITY CONFLICTING CASE (The Academic Confusion Test)": {
        "urls": [
            "https://wikipedia.org",   # 👈 DEEP FACTS LINK
            "https://wikipedia.org"  # 👈 DEEP FACTS LINK
        ],
        "llm_output_to_test": "Pluto is classified as a planet according to historical scientific records, meaning our solar system currently has nine official planets."
    }
}

def run_urop_test_suite():
    print("🚀 Initiating High-Complexity Novel Link Evaluation Testing Suite...\n")
    print("="*80)

    for name, payload in scenarios.items():
        print(f"\n🧪 RUNNING: {name}")
        print(f"🔗 Target URLs passed: {payload['urls']}")
        print(f"🤖 LLM Statement Tested: \"{payload['llm_output_to_test']}\"")
        
        start_time = time.time()
        try:
            response = requests.post(API_URL, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                res_data = response.json()
                print(f"⏱️ Local Computation Time: {elapsed:.2f} seconds")
                print(f"📊 --- FRAMEWORK METRIC REPORT ---")
                print(f"   🔹 Base Groundedness Score      : {res_data['groundedness_score']}")
                print(f"   🔹 Source Authority Multiplier  : {res_data['source_authority_multiplier']}")
                print(f"   🔹 Final Verified Trust Index   : {res_data['final_verified_trust_index']}")
                print(f"   📝 Academic Reasoning Summary   : {res_data['academic_reasoning']}")
            else:
                print(f"❌ Server Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"❌ Connection to local FastAPI failed: {e}")
            
        print("="*80)

if __name__ == "__main__":
    run_urop_test_suite()
