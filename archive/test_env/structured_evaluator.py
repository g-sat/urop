import asyncio
import requests
import json
from crawl4ai import AsyncWebCrawler

OLLAMA_JSON_URL = "http://localhost:11434/api/generate"

async def evaluate_with_json(target_url: str, llm_generated_answer: str):
    print(f"\n🌐 Phase 1: Scraping content...")
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=target_url)
        # Limit context size slightly so the 8B model doesn't get overwhelmed
        source_context = result.markdown[:4000] 

    # Constructing a system role prompt optimized for a smaller 8B model
    prompt_instruction = f"""
    [SYSTEM ROLE]
    You are a cold, precise validation bot. You output ONLY valid JSON. No conversational text.

    [TASK]
    Evaluate if the STATEMENT matches or is supported by the provided CONTEXT.

    [CONTEXT]
    {source_context}

    [STATEMENT]
    {llm_generated_answer}

    [REQUIRED JSON OUTPUT FORMAT]
    {{
        "score": 1.0 if completely true according to text, or 0.0 if false/not mentioned,
        "reason": "One short sentence explaining why"
    }}
    """

    print("🧠 Phase 2: Querying local Llama 3.1 using strict JSON Mode...")
    payload = {
        "model": "llama3.1",
        "prompt": prompt_instruction,
        "stream": False,
        "format": "json"  # 👈 This parameter forces Ollama to output valid JSON structure
    }

    try:
        response = requests.post(OLLAMA_JSON_URL, json=payload)
        if response.status_code == 200:
            raw_response = response.json().get("response")
            
            print("\n📊 --- Structured Verification Output ---")
            # Parse the text string back into a Python dictionary to verify structure
            parsed_json = json.loads(raw_response)
            print(json.dumps(parsed_json, indent=4))
            
        else:
            print(f"❌ Target processing error: {response.status_code}")
    except Exception as e:
        print(f"❌ Pipeline break: {e}")

if __name__ == "__main__":
    sample_url = "https://wikipedia.org"
    
    # We pass a completely fake fact to see if our structured judge accurately catches it!
    fake_statement = "Large language models were originally invented by the ancient Egyptians in 400 BC."
    
    asyncio.run(evaluate_with_json(sample_url, fake_statement))
