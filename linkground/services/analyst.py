from __future__ import annotations
import statistics
import httpx
from fastapi import HTTPException
from linkground.config import DEFAULT_ANALYST_MODEL, DEFAULT_JUDGE_RUNS, OLLAMA_CHAT_URL
from linkground.services.scoring import has_parseable_score, parse_groundedness
SYSTEM_PROMPT = 'You are a closed-book factual support scorer. Use only the provided source documents. Never chat, never ask questions, never apologize. Output only claim lines and a GROUNDEDNESS line in the required format. If a source is marked EVIDENCE_SOURCE: fallback, treat it as weak/unreliable evidence. If a source is marked WEIGHT: DISCOVERED_REDUCED_WEIGHT or ORIGIN: discovered, be more conservative — do not give SUPPORT above 0.70 unless the claim is clearly and specifically supported on that page.'

def build_user_prompt(source_context: str, statement: str, claim_count: int) -> str:
    return f'Use ONLY the source documents below. Ignore any prior knowledge.\n\n[SOURCE DOCUMENTS]\n{source_context}\n\n[STUDENT STATEMENT]\n{statement}\n\n[TASK]\nScore how strongly the sources support the student statement.\nEmit EXACTLY {claim_count} claim line(s).\nDo not split relative clauses into extra claims.\nFor mixed statements (one true half + one false half), emit two claims and score each half separately.\nDo not chat. Do not ask questions.\nIf evidence is marked fallback, do not give SUPPORT above 0.50 unless the claim is explicitly present there.\n\nSupport scale for each claim (continuous):\n- 0.90-1.00 clearly supported by live/cached page evidence (paraphrase OK)\n- 0.70-0.89 mostly supported; minor gap\n- 0.40-0.69 mixed / partly supported\n- 0.10-0.39 weakly related / not really supported\n- 0.00-0.09 contradicted or unsupported\n\n[REQUIRED OUTPUT FORMAT]\n- Claim: <short claim> -> SUPPORT: 0.XX because <one short source-based reason>\nGROUNDEDNESS: 0.XX\n\nGROUNDEDNESS must equal the mean of the SUPPORT scores, with two decimals.\n'

async def _chat(model_name: str, user_prompt: str) -> str:
    payload = {'model': model_name, 'stream': False, 'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user_prompt}], 'options': {'temperature': 0.0, 'num_predict': 320}}
    async with httpx.AsyncClient() as client:
        response = await client.post(OLLAMA_CHAT_URL, json=payload, timeout=90.0)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail='Local analyst model request failed.')
        body = response.json()
        message = body.get('message')
        if isinstance(message, dict):
            return message.get('content', '') or ''
        return body.get('response', '') or ''

async def _single_pass(source_context: str, statement: str, claim_count: int, analyst_model: str) -> tuple[float, str]:
    prompt = build_user_prompt(source_context, statement, claim_count)
    reasoning = await _chat(analyst_model, prompt)
    if not has_parseable_score(reasoning):
        print('[analyst] format miss; retrying once')
        retry_prompt = prompt + '\n\n[STRICT REMINDER]\nYour previous answer was invalid. Reply with ONLY the claim line(s) and GROUNDEDNESS: 0.XX. No other text.'
        reasoning = await _chat(analyst_model, retry_prompt)
    groundedness = parse_groundedness(reasoning, expected_claims=claim_count)
    return (groundedness, reasoning)

async def score_statement(source_context: str, statement: str, claim_count: int, model_name: str | None=None, judge_runs: int | None=None) -> tuple[float, str, float | None]:
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
        reasoning = f'{reasoning}\n[JUDGE_STABILITY] runs={runs} scores={scores} mean={mean_score} std={judge_std}'
    return (mean_score, reasoning, judge_std)
