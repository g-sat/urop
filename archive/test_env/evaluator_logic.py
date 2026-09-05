import asyncio
import requests
from crawl4ai import AsyncWebCrawler

OLLAMA_URL = "http://localhost:11434/api/generate"

async def evaluate_groundedness(target_url: str, llm_generated_answer: str):
    print(f"\n🌐 Phase 1: Ingesting knowledge from target link...")
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=target_url)
        # Isolate the clean text payload
        source_context = result.markdown

    # System instruction template specifying evaluation strictness
    prompt_instruction = f"""
    You are an objective AI Academic Evaluation Judge. Your task is to measure if a student's answer is supported by the source text provided.

    [SOURCE CONTEXT FROM LINK]
    {source_context}

    [STUDENT ANSWER TO TEST]
    {llm_generated_answer}

    CRITERIA:
    - Respond with a clear score between 0.0 (Complete Hallucination/Not in text) and 1.0 (100% Factually Accurate according to text).
    - Provide a single, short sentence detailing your reason.

    OUTPUT FORMAT (Strictly match this layout):
    Score: <score>
    Reason: <reason>
    """

    print("🧠 Phase 2: Processing verification via local Llama 3.1 model...")
    payload = {
        "model": "llama3.1",
        "prompt": prompt_instruction,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code == 200:
            print("\n📊 --- Local Evaluation Report ---")
            print(response.json().get("response"))
        else:
            print(f"❌ Target processing error: {response.status_code}")
    except Exception as e:
        print(f"❌ System failure connecting to Ollama: {e}")

# Let's run a test case right inside the script
if __name__ == "__main__":
    # URL to test against
    sample_url = "https://wikipedia.org"
    
    # Change this answer text to test if your judge model successfully flags true vs false facts!
    test_answer = "Large language models are evaluated using benchmarks like GLUE and SuperGLUE."
    
    asyncio.run(evaluate_groundedness(sample_url, test_answer))
