"""Rescore an existing linked-eval JSON via the live API (keeps claim split fixed)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API = "http://127.0.0.1:8000/v1/evaluate"


def score_one(statement: str, urls: list[str], model: str, mode: str) -> dict:
    if mode == "discovery":
        payload = {
            "urls": [],
            "statement": statement,
            "model": model,
            "judge_runs": 1,
            "discover_evidence": True,
            "discovery_depth": 0,
            "max_discovered_urls": 3,
        }
    elif mode == "hybrid":
        payload = {
            "urls": urls,
            "statement": statement,
            "model": model,
            "judge_runs": 1,
            "discover_evidence": True,
            "discovery_depth": 0,
            "max_discovered_urls": 3,
        }
    else:
        payload = {
            "urls": urls,
            "statement": statement,
            "model": model,
            "judge_runs": 1,
            "discover_evidence": False,
        }

    last_err = None
    for attempt in range(6):
        t0 = time.time()
        try:
            resp = requests.post(API, json=payload, timeout=120)
            latency = round(time.time() - t0, 2)
            if resp.status_code == 429 or (
                resp.status_code == 500 and "429" in (resp.text or "")
            ):
                time.sleep(10 * (attempt + 1))
                last_err = f"HTTP {resp.status_code}"
                continue
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}", "latency_seconds": latency}
            body = resp.json()
            return {
                "groundedness_score": body.get("groundedness_score"),
                "authority_multiplier": body.get("authority_multiplier"),
                "trust_index": body.get("trust_index"),
                "evidence_quality": body.get("evidence_quality"),
                "evidence_mode": body.get("evidence_mode"),
                "discovery_weight": body.get("discovery_weight"),
                "notes": body.get("notes", []),
                "analyst_reasoning": body.get("analyst_reasoning", ""),
                "latency_seconds": latency,
                "used_discovery": mode in {"discovery", "hybrid"},
                "evidence_strategy": mode,
            }
        except Exception as exc:
            last_err = str(exc)
            time.sleep(5 * (attempt + 1))
    return {"error": last_err or "failed", "latency_seconds": None}


def aggregate(rows: list[dict]) -> dict:
    scored = [r for r in rows if isinstance(r.get("groundedness_score"), (int, float))]
    if not scored:
        return {"claim_count": len(rows), "scored_count": 0}
    factual = [r for r in scored if r.get("claim_kind") != "meta"]
    out = {
        "claim_count": len(rows),
        "scored_count": len(scored),
        "failed_count": len(rows) - len(scored),
        "mean_groundedness": round(sum(float(r["groundedness_score"]) for r in scored) / len(scored), 3),
        "mean_trust_index": round(sum(float(r["trust_index"]) for r in scored) / len(scored), 3),
        "min_groundedness": min(float(r["groundedness_score"]) for r in scored),
        "max_groundedness": max(float(r["groundedness_score"]) for r in scored),
        "mean_claim_latency": round(
            sum(float(r["latency_seconds"]) for r in scored if r.get("latency_seconds")) / max(1, len(scored)),
            2,
        ),
    }
    if factual:
        out["mean_groundedness_factual"] = round(
            sum(float(r["groundedness_score"]) for r in factual) / len(factual), 3
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.getenv("DEFAULT_ANALYST_MODEL", "openai/gpt-oss-20b"))
    parser.add_argument("--sleep", type=float, default=2.5, help="seconds between claims")
    args = parser.parse_args()

    src = json.loads(args.from_json.read_text(encoding="utf-8"))
    claims = src.get("claims") or []
    t0 = time.time()
    rows = []
    print(f"rescoring {len(claims)} claims with {args.model}")
    for i, claim in enumerate(claims, 1):
        mode = claim.get("evidence_strategy") or ("discovery" if claim.get("used_discovery") else "caller")
        if mode not in {"caller", "discovery", "hybrid"}:
            mode = "caller"
        scored = score_one(claim["statement"], claim.get("urls") or [], args.model, mode)
        row = {**claim, **scored}
        rows.append(row)
        if "error" in scored:
            print(f"[{i}/{len(claims)}] {claim.get('id')} fail {scored['error'][:80]}")
        else:
            print(
                f"[{i}/{len(claims)}] {claim.get('id')}  "
                f"g={row['groundedness_score']}  t={row['trust_index']}  "
                f"{row['latency_seconds']}s"
            )
        time.sleep(args.sleep)

    wall = round(time.time() - t0, 2)
    summary = aggregate(rows)
    report = {
        "answer_file": src.get("answer_file"),
        "model": args.model,
        "source_claims_from": str(args.from_json),
        "wall_seconds": wall,
        "summary": summary,
        "claims": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"mean_g={summary.get('mean_groundedness')}  "
        f"failed={summary.get('failed_count')}  "
        f"wall={wall}s  mean_claim={summary.get('mean_claim_latency')}s  "
        f"-> {args.output}"
    )


if __name__ == "__main__":
    main()
