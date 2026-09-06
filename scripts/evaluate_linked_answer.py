"""
Automatically evaluate an LLM answer with claim → link pairing.

Pipeline:
  1. Collect a URL pool (from the answer text and/or --urls / --urls-file)
  2. Ask a local Ollama model to split the answer into atomic claims
  3. Ask it to assign each claim to the best matching URL(s) from the pool
  4. Score each claim against its assigned URL(s) via LinkGround
  5. Aggregate continuous groundedness / authority / trust

Examples:
  python scripts/evaluate_linked_answer.py --answer-file scripts/threejs_statement.txt --urls-file scripts/threejs_url_pool.txt
  python scripts/evaluate_linked_answer.py --answer-file answer.txt --url https://a.com --url https://b.com
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API = "http://127.0.0.1:8000/v1/evaluate"
DEFAULT_HEALTH = "http://127.0.0.1:8000/health"
DEFAULT_OLLAMA = "http://127.0.0.1:11434/api/chat"
URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.IGNORECASE)


def normalize_url(url: str) -> str:
    cleaned = url.strip().rstrip(".,);]")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return cleaned


def extract_urls_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.findall(text or ""):
        try:
            url = normalize_url(match)
        except ValueError:
            continue
        if url not in seen:
            seen.add(url)
            found.append(url)
    return found


def load_url_pool(answer_text: str, urls: list[str] | None, urls_file: Path | None) -> list[str]:
    pool: list[str] = []
    seen: set[str] = set()

    def add_many(items: list[str]) -> None:
        for item in items:
            try:
                url = normalize_url(item)
            except ValueError:
                continue
            if url not in seen:
                seen.add(url)
                pool.append(url)

    add_many(extract_urls_from_text(answer_text))
    if urls:
        add_many(urls)
    if urls_file:
        lines = [
            line.strip()
            for line in urls_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        add_many(lines)

    return pool


def ollama_chat(model: str, system: str, user: str, ollama_url: str) -> str:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.0, "num_predict": 1200},
    }
    response = requests.post(ollama_url, json=payload, timeout=180)
    response.raise_for_status()
    body = response.json()
    message = body.get("message")
    if isinstance(message, dict):
        return message.get("content", "") or ""
    return body.get("response", "") or ""


def extract_json_payload(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty model response")

    fence = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return json.loads(fence.group(1))

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_obj, end_obj = text.find("{"), text.rfind("}")
    if start_obj != -1 and end_obj > start_obj:
        return json.loads(text[start_obj : end_obj + 1])

    start_arr, end_arr = text.find("["), text.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        return json.loads(text[start_arr : end_arr + 1])

    raise ValueError(f"Could not parse JSON from model output: {text[:300]!r}")


def propose_missing_urls(answer_text: str, model: str, ollama_url: str) -> list[str]:
    """
    When the answer names sites without embedding URLs, ask the local model
    for likely official/gallery URLs. These are candidates only; scoring still
    happens against crawled page evidence.
    """
    system = (
        "You extract website names from text and propose their most likely official "
        "or gallery URLs. Return JSON only."
    )
    user = f"""From the answer below, list named websites, products, or galleries and propose
the best public URL for each (official site or well-known awards/gallery page).

Return ONLY JSON:
{{
  "entities": [
    {{"name": "...", "url": "https://..."}}
  ]
}}

ANSWER:
{answer_text}
"""
    raw = ollama_chat(model, system, user, ollama_url)
    data = extract_json_payload(raw)
    entities = data.get("entities", []) if isinstance(data, dict) else data
    urls: list[str] = []
    for item in entities or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if isinstance(url, str):
            try:
                urls.append(normalize_url(url))
            except ValueError:
                continue
    return urls


def split_and_assign_claims(
    answer_text: str,
    url_pool: list[str],
    model: str,
    ollama_url: str,
) -> list[dict[str, Any]]:
    system = (
        "You are a claim decomposition and evidence-routing engine. "
        "Return JSON only. Never chat."
    )
    numbered_urls = "\n".join(f"{index}. {url}" for index, url in enumerate(url_pool))
    user = f"""Split the ANSWER into atomic factual claims.
Assign each claim to the 1-2 best matching URLs from URL_POOL.

Matching rules:
- Only use indexes from URL_POOL.
- Match by entity name in the claim to the URL path/domain
  (e.g. Casa di Solare -> casa-di-solare URL, RelicVault -> relicvault URL,
  Awwwards gallery -> awwwards.com/websites/three-js, rankings -> rankings URL).
- Do NOT assign a claim about site A to a page about site B.
- Prefer the most specific supporting page over a generic homepage.
- If unsure, pick the closest gallery/ranking page rather than an unrelated nominee page.

Return ONLY JSON:
{{
  "claims": [
    {{
      "id": "C01",
      "statement": "one atomic claim",
      "url_indexes": [0]
    }}
  ]
}}

URL_POOL:
{numbered_urls}

ANSWER:
{answer_text}
"""
    raw = ollama_chat(model, system, user, ollama_url)
    data = extract_json_payload(raw)
    claims_raw = data.get("claims", []) if isinstance(data, dict) else data

    claims: list[dict[str, Any]] = []
    for index, item in enumerate(claims_raw or [], start=1):
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement") or "").strip()
        if not statement:
            continue

        indexes = item.get("url_indexes") or item.get("urls") or []
        assigned: list[str] = []
        for value in indexes:
            if isinstance(value, int) and 0 <= value < len(url_pool):
                assigned.append(url_pool[value])
            elif isinstance(value, str):
                try:
                    candidate = normalize_url(value)
                except ValueError:
                    continue
                if candidate in url_pool:
                    assigned.append(candidate)

        # De-duplicate while preserving order
        deduped: list[str] = []
        seen: set[str] = set()
        for url in assigned:
            if url not in seen:
                seen.add(url)
                deduped.append(url)

        if not deduped:
            # Fallback: first URL in pool so evaluation can still run
            deduped = [url_pool[0]]

        claim_id = str(item.get("id") or f"C{index:02d}")
        claims.append(
            {
                "id": claim_id,
                "statement": statement,
                "urls": deduped[:2],
            }
        )
    return claims


def score_claim(api_url: str, statement: str, urls: list[str], model: str) -> dict[str, Any]:
    started = time.time()
    response = requests.post(
        api_url,
        json={
            "urls": urls,
            "statement": statement,
            "model": model,
        },
        timeout=180,
    )
    latency = round(time.time() - started, 2)
    if response.status_code != 200:
        return {
            "error": f"HTTP {response.status_code}: {response.text[:300]}",
            "latency_seconds": latency,
        }
    body = response.json()
    return {
        "groundedness_score": body.get("groundedness_score"),
        "authority_multiplier": body.get("authority_multiplier"),
        "trust_index": body.get("trust_index"),
        "per_url_authority": body.get("per_url_authority", []),
        "analyst_reasoning": body.get("analyst_reasoning", ""),
        "latency_seconds": latency,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        row
        for row in rows
        if isinstance(row.get("groundedness_score"), (int, float))
    ]
    if not scored:
        return {
            "claim_count": len(rows),
            "scored_count": 0,
            "mean_groundedness": None,
            "mean_authority": None,
            "mean_trust_index": None,
        }
    return {
        "claim_count": len(rows),
        "scored_count": len(scored),
        "mean_groundedness": round(
            sum(float(row["groundedness_score"]) for row in scored) / len(scored), 3
        ),
        "mean_authority": round(
            sum(float(row["authority_multiplier"]) for row in scored) / len(scored), 3
        ),
        "mean_trust_index": round(
            sum(float(row["trust_index"]) for row in scored) / len(scored), 3
        ),
        "min_groundedness": min(float(row["groundedness_score"]) for row in scored),
        "max_groundedness": max(float(row["groundedness_score"]) for row in scored),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-split an LLM answer into claim→link pairs and evaluate via LinkGround."
    )
    parser.add_argument("--answer-file", type=Path, required=True, help="Path to the LLM answer text")
    parser.add_argument("--urls-file", type=Path, default=None, help="Optional newline-separated URL pool")
    parser.add_argument("--url", action="append", default=[], help="Add a URL to the evidence pool")
    parser.add_argument(
        "--propose-urls",
        action="store_true",
        help="If the answer lacks URLs, ask Ollama to propose candidate URLs for named sites",
    )
    parser.add_argument("--model", default="llama3.1", help="Ollama model for split/assign + LinkGround analyst")
    parser.add_argument("--api-url", default=DEFAULT_API)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "linked_answer_eval.json",
        help="Where to write the JSON report",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    answer_text = args.answer_file.read_text(encoding="utf-8").strip()
    if not answer_text:
        raise SystemExit("Answer file is empty.")

    try:
        health = requests.get(args.health_url, timeout=5)
        print(f"[linked-eval] API health: {health.json()}")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"LinkGround API not reachable at {args.health_url}: {exc}") from exc

    url_pool = load_url_pool(answer_text, args.url, args.urls_file)
    if args.propose_urls or not url_pool:
        print("[linked-eval] proposing candidate URLs from named entities...")
        proposed = propose_missing_urls(answer_text, args.model, args.ollama_url)
        for url in proposed:
            if url not in url_pool:
                url_pool.append(url)

    if not url_pool:
        raise SystemExit(
            "No URLs available. Pass --urls-file / --url, embed links in the answer, "
            "or use --propose-urls."
        )

    print(f"[linked-eval] URL pool size: {len(url_pool)}")
    for index, url in enumerate(url_pool):
        print(f"  [{index}] {url}")

    print("[linked-eval] splitting answer into claims and assigning URLs...")
    claims = split_and_assign_claims(answer_text, url_pool, args.model, args.ollama_url)
    if not claims:
        raise SystemExit("Model returned no claims.")

    print(f"[linked-eval] claims: {len(claims)}")
    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claims, start=1):
        print(f"\n[linked-eval] {claim['id']} ({index}/{len(claims)})")
        print(f"  statement: {claim['statement'][:120]}")
        print(f"  urls: {claim['urls']}")
        scored = score_claim(args.api_url, claim["statement"], claim["urls"], args.model)
        row = {**claim, **scored}
        rows.append(row)
        if "error" in row:
            print(f"  ERROR: {row['error']}")
        else:
            print(
                f"  groundedness={row['groundedness_score']} "
                f"authority={row['authority_multiplier']} "
                f"trust={row['trust_index']} "
                f"latency={row['latency_seconds']}s"
            )

    summary = aggregate(rows)
    report = {
        "answer_file": str(args.answer_file),
        "model": args.model,
        "url_pool": url_pool,
        "summary": summary,
        "claims": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 72)
    print("AUTOMATED CLAIM->LINK EVALUATION SUMMARY")
    print("=" * 72)
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
