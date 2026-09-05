import asyncio
import requests
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from crawl4ai import AsyncWebCrawler

app = FastAPI(
    title="UROP Local LLM Evaluation API",
    description="An open-source link-based LLM groundedness evaluator running locally."
)

OLLAMA_JSON_URL = "http://localhost:11434/api/generate"

# Define what data our API expects to receive from the client
class EvaluationRequest(BaseModel):
    url: HttpUrl
    statement: str

# Define the exact data structure our API returns
class EvaluationResponse(BaseModel):
    score: float
    reason: str

async def process_local_eval(url: str, statement: str) -> dict:
    """Scrapes a URL and uses local Llama 3.1 to grade an assertion."""
    # Step 1: Scrape text
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url)
        if not result or not result.markdown:
            raise HTTPException(status_code=400, detail="Unable to extract readable text from link.")
        source_context = result.markdown[:4000] # Limit token length for memory safety

    # Step 2: Formulate System Instruction Prompt
    prompt_instruction = f"""
    [SYSTEM ROLE]
    You are a cold, precise validation bot. You output ONLY valid JSON. No conversational text.

    [TASK]
    Evaluate if the STATEMENT matches or is supported by the provided CONTEXT.

    [CONTEXT]
    {source_context}

    [STATEMENT]
    {statement}

    [REQUIRED JSON OUTPUT FORMAT]
    {{
        "score": 1.0 if completely true according to text, or 0.0 if false/not mentioned,
        "reason": "One short sentence explaining why"
    }}
    """

    # Step 3: Hit local Ollama
    payload = {
        "model": "llama3.1",
        "prompt": prompt_instruction,
        "stream": False,
        "format": "json"
    }

    try:
        response = requests.post(OLLAMA_JSON_URL, json=payload, timeout=30)
        if response.status_code == 200:
            raw_response = response.json().get("response")
            return json.loads(raw_response)
        else:
            raise HTTPException(status_code=500, detail=f"Ollama server returned error: {response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline exception: {str(e)}")


@app.post("/v1/evaluate", response_model=EvaluationResponse)
async def evaluate_link_alignment(payload: EvaluationRequest):
    # Trigger the evaluation workflow asynchronously
    result = await process_local_eval(str(payload.url), payload.statement)
    
    # Return the clean dictionary matching our Pydantic schema layout
    return EvaluationResponse(
        score=result.get("score", 0.0),
        reason=result.get("reason", "Evaluation parsing failed.")
    )

if __name__ == "__main__":
    import uvicorn
    # Launch the local Uvicorn development server
    uvicorn.run(app, host="127.0.0.1", port=8000)

