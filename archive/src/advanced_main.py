import json
import httpx
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List
from crawl4ai import AsyncWebCrawler

app = FastAPI(
    title="UROP: Multi-Agent Fractional Link Evaluation API",
    description="Deterministic multi-stage pipeline utilizing Python math logic arrays for absolute stability."
)

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

class AdvancedEvalRequest(BaseModel):
    urls: List[HttpUrl]
    llm_output_to_test: str

class AdvancedEvalResponse(BaseModel):
    groundedness_score: float
    source_authority_multiplier: float
    final_verified_trust_index: float
    academic_reasoning: str

def calculate_domain_authority(url: str) -> float:
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    if any(domain.endswith(ext) for ext in [".edu", ".gov", ".org"]):
        return 1.2
    elif "wikipedia.org" in domain or "github.com" in domain:
        return 1.1
    return 1.0

@app.post("/v2/evaluate-provenance", response_model=AdvancedEvalResponse)
async def evaluate_provenance_and_truth(payload: AdvancedEvalRequest):
    # 1. Compute link structural authority
    authority_multipliers = [calculate_domain_authority(str(u)) for u in payload.urls]
    mean_authority = sum(authority_multipliers) / len(authority_multipliers)

    # 2. Concurrently scrape the source targets
    async with AsyncWebCrawler(verbose=False) as crawler:
        aggregated_context = ""
        for i, url in enumerate(payload.urls):
            result = await crawler.arun(url=str(url))
            if result and result.markdown:
                clean_text = result.markdown[:3000]
                aggregated_context += f"\n[SOURCE DOCUMENT {i+1} | URL: {str(url)}]\n{clean_text}\n"

    # 3. FIXING SEMANTIC LEAKAGE BUG (ACTION ITEM 3)
    # Injecting the aggressive negative constraints guardrail directly into the Analyst prompt frame.
    analyst_prompt = f"""
    [CRITICAL SYSTEM DIRECTIVE: STRICT CLOSED-CONTEXT GROUNDING ONLY]
    You are a robotic, closed-book data validation checker. You have NO external knowledge. You have NO memory outside the text provided below.
    Your sole task is to evaluate if the STUDENT STATEMENT can be explicitly verified by the [SOURCE DOCUMENTS] text.
    
    [STRICT EVALUATION BOUNDARY RULES]:
    1. If a claim is a 'widely known fact in the real world' but NOT explicitly typed in the [SOURCE DOCUMENTS] block below, you are ordered to mark it as -> [FALSE]. Do not use your memory under any condition.
    2. If the [SOURCE DOCUMENTS] text is brief, missing details, or doesn't mention a claim, that claim MUST be marked as -> [FALSE].
    3. You are strictly forbidden from writing paragraph-style conclusions or echoing instructions.
    
    Break the STUDENT STATEMENT into distinct factual claims. For each claim, determine if it is explicitly supported by the text or if it is false/unmentioned.
    Format each line exactly like this template:
    - Claim: [Short claim text] -> [TRUE] or [FALSE] because [Write a short sentence citing the text, or stating that the text does not mention it]

    [SOURCE DOCUMENTS]
    {aggregated_context}

    [STUDENT STATEMENT TO TEST]
    {payload.llm_output_to_test}
    """

    ollama_payload = {
        "model": "llama3.1",
        "prompt": analyst_prompt,
        "stream": False
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OLLAMA_GENERATE_URL, json=ollama_payload, timeout=90.0)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Local inference node dropped request.")
                
            model_analysis_text = response.json().get("response", "")
            
            # 4. Stage 2 Deterministic Math Processing: Use Python code to calculate fractional scores
            lines = model_analysis_text.split('\n')
            true_count = 0
            false_count = 0
            
            for line in lines:
                if "-> [TRUE]" in line:
                    true_count += 1
                elif "-> [FALSE]" in line:
                    false_count += 1
            
            total_claims = true_count + false_count
            
            if total_claims == 0:
                if "true" in model_analysis_text.lower() and "false" not in model_analysis_text.lower():
                    groundedness_score = 1.0
                elif "false" in model_analysis_text.lower() and "true" not in model_analysis_text.lower():
                    groundedness_score = 0.0
                else:
                    groundedness_score = 0.5
            else:
                groundedness_score = round(true_count / total_claims, 2)
                
            final_trust_index = min(1.0, round(groundedness_score * mean_authority, 2))
            
            return AdvancedEvalResponse(
                groundedness_score=groundedness_score,
                source_authority_multiplier=round(mean_authority, 2),
                final_verified_trust_index=final_trust_index,
                academic_reasoning=model_analysis_text
            )
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Pipeline error exception logs: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
