"""Local Ollama analyst that assigns continuous support scores."""

from __future__ import annotations

import httpx
from fastapi import HTTPException

from linkground.config import DEFAULT_ANALYST_MODEL, OLLAMA_CHAT_URL
from linkground.services.scoring import has_parseable_score, parse_groundedness

SYSTEM_PROMPT = (
    "You are a closed-book factual support scorer. "
    "Use only the provided source documents. "
    "Never chat, never ask questions, never apologize. "
    "Output only claim lines and a GROUNDEDNESS line in the required format."
)


def build_user_prompt(source_context: str, statement: str, claim_count: int) -> str:
    return f"""Use ONLY the source documents below. Ignore any prior knowledge.

[SOURCE DOCUMENTS]
{source_context}

[STUDENT STATEMENT]
{statement}

[TASK]
Score how strongly the sources support the student statement.
Emit EXACTLY {claim_count} claim line(s).
Do not split relative clauses into extra claims.
Do not chat. Do not ask questions.

Support scale for each claim (continuous):
- 0.90-1.00 clearly supported (paraphrase OK)
- 0.70-0.89 mostly supported; minor gap
- 0.40-0.69 mixed / partly supported
- 0.10-0.39 weakly related / not really supported
- 0.00-0.09 contradicted or unsupported

[REQUIRED OUTPUT FORMAT]
- Claim: <short claim> -> SUPPORT: 0.XX because <one short source-based reason>
GROUNDEDNESS: 0.XX

GROUNDEDNESS must equal the mean of the SUPPORT scores, with two decimals.
"""


async def _chat(model_name: str, user_prompt: str) -> str:
    payload = {
        "model": model_name,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.0,
            "num_predict": 280,
        },
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(OLLAMA_CHAT_URL, json=payload, timeout=90.0)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Local analyst model request failed.")
        body = response.json()
        message = body.get("message")
        if isinstance(message, dict):
            return message.get("content", "") or ""
        return body.get("response", "") or ""


async def score_statement(
    source_context: str,
    statement: str,
    claim_count: int,
    model_name: str | None = None,
) -> tuple[float, str]:
    """
    Return (groundedness_score, analyst_reasoning).

    Retries once if the model ignores the required output format.
    """
    analyst_model = model_name or DEFAULT_ANALYST_MODEL
    prompt = build_user_prompt(source_context, statement, claim_count)
    reasoning = await _chat(analyst_model, prompt)

    if not has_parseable_score(reasoning):
        print("[analyst] format miss; retrying once")
        retry_prompt = (
            prompt
            + "\n\n[STRICT REMINDER]\nYour previous answer was invalid. "
            "Reply with ONLY the claim line(s) and GROUNDEDNESS: 0.XX. No other text."
        )
        reasoning = await _chat(analyst_model, retry_prompt)

    groundedness = parse_groundedness(reasoning, expected_claims=claim_count)
    return groundedness, reasoning
