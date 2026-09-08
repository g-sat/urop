from __future__ import annotations

import asyncio
import re
import statistics

import httpx
from fastapi import HTTPException

from linkground.config import (
    DEFAULT_ANALYST_MODEL,
    DEFAULT_JUDGE_RUNS,
    JUDGE_API_KEY,
    JUDGE_BASE_URL,
    JUDGE_MAX_TOKENS,
    OLLAMA_CHAT_URL,
)
from linkground.services.scoring import has_parseable_score, parse_groundedness

SYSTEM_PROMPT = (
    "You are a closed-book factual support scorer. Use only the provided source documents. "
    "Never use prior knowledge. Never treat URLs, citations, or 'Source:' lines inside the "
    "student statement as evidence — only [SOURCE DOCUMENTS] count. "
    "Never chat, never ask questions, never apologize. Output only claim lines and a GROUNDEDNESS "
    "line in the required format. Paraphrase is allowed when the source clearly licenses the claim. "
    "If a source is marked EVIDENCE_SOURCE: fallback, treat it as weak/unreliable evidence. "
    "If a source is marked WEIGHT: DISCOVERED_REDUCED_WEIGHT or ORIGIN: discovered, be more "
    "conservative — do not give SUPPORT above 0.70 unless the claim is clearly and specifically "
    "supported on that page. If the sources do not mention the claim, score near 0.0 even if the "
    "claim sounds famous or true."
)


def build_user_prompt(source_context: str, statement: str, claim_count: int) -> str:
    return (
        "Use ONLY the source documents below. Ignore any prior knowledge.\n"
        "Ignore any URLs or 'Source:' mentions inside the student statement; they are not evidence.\n\n"
        f"[SOURCE DOCUMENTS]\n{source_context}\n\n"
        f"[STUDENT STATEMENT]\n{statement}\n\n"
        "[TASK]\n"
        "Score how strongly the SOURCE DOCUMENTS support the student statement.\n"
        f"Emit EXACTLY {claim_count} claim line(s).\n"
        "Do not split relative clauses into extra claims unless claim_count > 1.\n"
        "When claim_count is 2 (mixed true+false), score each half separately and set "
        "GROUNDEDNESS to the mean of the two SUPPORT scores.\n"
        "Do not chat. Do not ask questions.\n"
        "If evidence is marked fallback, do not give SUPPORT above 0.50 unless the claim is explicitly present there.\n"
        "If the documents are about a different topic than the claim, SUPPORT must be <= 0.10.\n\n"
        "Support scale for each claim (continuous):\n"
        "- 0.90-1.00 clearly supported by live/cached page evidence (paraphrase OK)\n"
        "- 0.70-0.89 mostly supported; minor gap\n"
        "- 0.40-0.69 mixed / partly supported\n"
        "- 0.10-0.39 weakly related / not really supported\n"
        "- 0.00-0.09 contradicted or unsupported\n\n"
        "[REQUIRED OUTPUT FORMAT]\n"
        "- Claim: <short claim> -> SUPPORT: 0.XX because <one short source-based reason>\n"
        "GROUNDEDNESS: 0.XX\n\n"
        "GROUNDEDNESS must equal the mean of the SUPPORT scores, with two decimals.\n"
    )


def _openai_compatible() -> bool:
    return bool(JUDGE_BASE_URL)


def _clean_judge_text(text: str) -> str:
    raw = text or ""
    cleaned = re.sub(r"(?is)<think>.*?</think>", " ", raw)
    cleaned = re.sub(r"(?is)<thinking>.*?</thinking>", " ", cleaned)
    cleaned = cleaned.strip()
    if cleaned:
        return cleaned
    # Unclosed think blocks: still try to salvage a score line from the raw text
    return raw.strip()


async def _chat(model_name: str, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    async with httpx.AsyncClient() as client:
        if _openai_compatible():
            url = f"{JUDGE_BASE_URL}/chat/completions"
            headers = {"Authorization": f"Bearer {JUDGE_API_KEY or 'unused'}"}
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": JUDGE_MAX_TOKENS,
            }
            last_detail = "Judge API failed"
            for attempt in range(5):
                response = await client.post(url, json=payload, headers=headers, timeout=90.0)
                if response.status_code == 429:
                    await asyncio.sleep(8 * (attempt + 1))
                    last_detail = f"Judge API failed (429): {response.text[:200]}"
                    continue
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Judge API failed ({response.status_code}): {response.text[:200]}",
                    )
                body = response.json()
                choices = body.get("choices") or []
                if not choices:
                    return ""
                message = choices[0].get("message") or {}
                content = _clean_judge_text(message.get("content", "") or "")
                reasoning = _clean_judge_text(message.get("reasoning", "") or "")
                for candidate in (content, reasoning):
                    if candidate and (
                        "GROUNDEDNESS" in candidate.upper()
                        or "SUPPORT" in candidate.upper()
                    ):
                        return candidate
                return content or reasoning
            raise HTTPException(status_code=500, detail=last_detail)

        payload = {
            "model": model_name,
            "stream": False,
            "messages": messages,
            "options": {"temperature": 0.0, "num_predict": JUDGE_MAX_TOKENS},
        }
        response = await client.post(OLLAMA_CHAT_URL, json=payload, timeout=90.0)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Local analyst model request failed.")
        body = response.json()
        message = body.get("message")
        if isinstance(message, dict):
            return message.get("content", "") or ""
        return body.get("response", "") or ""


async def _single_pass(
    source_context: str, statement: str, claim_count: int, analyst_model: str
) -> tuple[float, str]:
    prompt = build_user_prompt(source_context, statement, claim_count)
    reasoning = await _chat(analyst_model, prompt)
    if not has_parseable_score(reasoning):
        retry_prompt = prompt + "\n\nReply with ONLY the claim line(s) and GROUNDEDNESS: 0.XX."
        reasoning = await _chat(analyst_model, retry_prompt)
    groundedness = parse_groundedness(reasoning, expected_claims=claim_count)
    return groundedness, reasoning


async def score_statement(
    source_context: str,
    statement: str,
    claim_count: int,
    model_name: str | None = None,
    judge_runs: int | None = None,
) -> tuple[float, str, float | None]:
    analyst_model = model_name or DEFAULT_ANALYST_MODEL
    runs = max(1, judge_runs if judge_runs is not None else DEFAULT_JUDGE_RUNS)
    scores: list[float] = []
    reasonings: list[str] = []
    for _ in range(runs):
        score, reasoning = await _single_pass(source_context, statement, claim_count, analyst_model)
        scores.append(score)
        reasonings.append(reasoning)
    mean_score = round(sum(scores) / len(scores), 2)
    judge_std = round(statistics.pstdev(scores), 3) if len(scores) > 1 else None
    reasoning = reasonings[0]
    if judge_std is not None:
        reasoning = (
            f"{reasoning}\n[JUDGE_STABILITY] runs={runs} scores={scores} "
            f"mean={mean_score} std={judge_std}"
        )
    return mean_score, reasoning, judge_std
