import json
import httpx
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import List
from crawl4ai import AsyncWebCrawler

app = FastAPI(
    title="UROP: Multi-Link & Sliding Window Evaluation API",
    description="Advanced open-source framework handling concurrent scraping, sliding windows, and multi-link evaluation."
)

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

class MultiEvalRequest(BaseModel):
    urls: List[HttpUrl]  # Supports evaluating multiple links simultaneously
    statement: str

class SourceDetail(BaseModel):
    url: str
    status: str
    chunks_processed: int

class MultiEvalResponse(BaseModel):
    score: float
    reason: str
    sources_analyzed: List[SourceDetail]

def sliding_window_splitter(text: str, window_size: int = 1500, overlap: int = 300) -> List[str]:
    """
    Implements a strict rolling/sliding window text splitter.
    Ensures long articles are chunked cleanly without breaking factual statements.
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    if text_length <= window_size:
        return [text]
        
    while start < text_length:
        end = start + window_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Shift window forward by the size minus overlap
        start += (window_size - overlap)
        
    return chunks

async def fetch_and_chunk_url(crawler: AsyncWebCrawler, url: str) -> dict:
    """Scrapes a single URL and splits it safely into semantic sliding windows."""
    try:
        result = await crawler.arun(url=url)
        if not result or not result.markdown:
            return {"url": url, "status": "Failed", "chunks": []}
        
        # Apply the sliding window splitter to handle extremely long web files safely
        text_chunks = sliding_window_splitter(result.markdown, window_size=1800, overlap=300)
        
        # Guard: Only keep top 3 chunks per link to prevent local VRAM overflow
        return {"url": url, "status": "Success", "chunks": text_chunks[:3]}
    except Exception:
        return {"url": url, "status": "Error Exception", "chunks": []}

@app.post("/v1/evaluate-multi", response_model=MultiEvalResponse)
async def evaluate_multi_links(payload: MultiEvalRequest):
    # 1. Scraping all links simultaneously using asyncio.gather
    async with AsyncWebCrawler(verbose=False) as crawler:
        tasks = [fetch_and_chunk_url(crawler, str(url)) for url in payload.urls]
        scraping_results = await asyncio.gather(*tasks)

    # Compile the sources context information safely for our system prompt
    aggregated_context = ""
    sources_summary_log = []
    
    for i, res in enumerate(scraping_results):
        sources_summary_log.append(SourceDetail(
            url=res["url"],
            status=res["status"],
            chunks_processed=len(res["chunks"])
        ))
        
        for j, chunk in enumerate(res["chunks"]):
            aggregated_context += f"\n--- SOURCE [{i+1}] LINK: {res['url']} (WINDOW SECTOR {j+1}) ---\n{chunk}\n"

    if not aggregated_context.strip():
        raise HTTPException(status_code=400, detail="Could not retrieve text from any of the provided URLs.")

    # 2. Formulate Multi-Link Cross Comparison Prompt Instructions
    prompt = f"""
    [SYSTEM ROLE]
    You are an advanced multi-document verification agent. You output ONLY valid JSON. No conversational text.

    [TASK]
    Evaluate if the STATEMENT matches, contradicts, or is completely unsupported across the multiple provided contexts.
    Cross-reference facts between the distinct source window sectors.

    [AGGREGATED MULTI-LINK CONTEXT]
    {aggregated_context}

    [STATEMENT TO MEASURE]
    {payload.statement}

    [REQUIRED JSON OUTPUT FORMAT]
    {{
        "score": 1.0 if the statement is factually aligned with the links, 0.5 if partially true, or 0.0 if entirely unmentioned/false,
        "reason": "Provide a concise comparative explanation referencing which sources support or contradict the claim."
    }}
    """

    # 3. Request inference via your local Ollama Llama 3.1 node
    ollama_payload = {
        "model": "llama3.1",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OLLAMA_GENERATE_URL, json=ollama_payload, timeout=60.0)
            if response.status_code == 200:
                raw_text = response.json().get("response", "{}")
                evaluation_data = json.loads(raw_text)
                
                return MultiEvalResponse(
                    score=evaluation_data.get("score", 0.0),
                    reason=evaluation_data.get("reason", "Failed processing output parsing."),
                    sources_analyzed=sources_summary_log
                )
            else:
                raise HTTPException(status_code=500, detail=f"Ollama node processing failure status: {response.status_code}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Inference pipeline break: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
