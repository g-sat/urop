"""Run the paper benchmark against a live LinkGround API.

Default dataset: data/paper_benchmark.jsonl (long linked answers).
Judge model defaults to DEFAULT_ANALYST_MODEL from .env (LLM7 / Groq / Ollama).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

API = os.getenv("API_EVAL_URL", "http://127.0.0.1:8000/v1/evaluate")
HEALTH = os.getenv("API_HEALTH_URL", "http://127.0.0.1:8000/health")
DEFAULT_DATASET = ROOT / "data" / "paper_benchmark.jsonl"
DEFAULT_OUT = ROOT / "results" / "benchmark_metrics.csv"


def load_cases(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if not isinstance(data, list):
        raise SystemExit(f"dataset must be a list: {path}")
    return data


def expected_score(case: dict) -> float:
    if "label_support" in case:
        return float(case["label_support"])
    if "expected_score" in case:
        return float(case["expected_score"])
    raise KeyError("case needs label_support or expected_score")


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if r.get("groundedness_score") is not None]
    if not ok:
        return {"n": 0}
    g = [float(r["groundedness_score"]) for r in ok]
    exp = [float(r["expected_score"]) for r in ok]
    mae = sum(abs(a - b) for a, b in zip(g, exp)) / len(ok)
    out: dict = {
        "n": len(rows),
        "scored": len(ok),
        "mae_support": round(mae, 4),
        "mean_latency": round(sum(float(r["latency_seconds"]) for r in ok) / len(ok), 2),
        "mean_groundedness": round(sum(g) / len(g), 3),
    }

    pairs: dict[str, dict[str, dict]] = {}
    for r in ok:
        pid = r.get("pair_id")
        cond = r.get("condition")
        if pid and cond in {"supported", "swapped", "matched"}:
            key = "matched" if cond == "supported" else cond
            pairs.setdefault(str(pid), {})[key] = r
    deltas = []
    for pid, parts in pairs.items():
        m = parts.get("matched") or parts.get("supported")
        s = parts.get("swapped")
        if m and s:
            deltas.append(float(m["groundedness_score"]) - float(s["groundedness_score"]))
    if deltas:
        out["n_swap_pairs"] = len(deltas)
        out["mean_swap_delta"] = round(sum(deltas) / len(deltas), 3)
        out["swap_delta_min"] = round(min(deltas), 3)
        out["swap_delta_max"] = round(max(deltas), 3)

    by_cond: dict[str, list[float]] = {}
    for r in ok:
        cond = str(r.get("condition") or "unknown")
        by_cond.setdefault(cond, []).append(float(r["groundedness_score"]))
    out["mean_g_by_condition"] = {
        k: round(sum(v) / len(v), 3) for k, v in sorted(by_cond.items())
    }
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LinkGround paper benchmark.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--model",
        default=os.getenv("DEFAULT_ANALYST_MODEL", "mistral-Nemo-Instruct-2407"),
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all cases")
    parser.add_argument("--sleep", type=float, default=2.0, help="seconds between calls")
    parser.add_argument("--judge-runs", type=int, default=1)
    parser.add_argument("--discover-evidence", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        requests.get(HEALTH, timeout=5).raise_for_status()
    except Exception as exc:
        raise SystemExit(f"API down at {HEALTH}: {exc}") from exc

    if not args.dataset.exists():
        raise SystemExit(
            f"missing {args.dataset} — run: python scripts/build_paper_dataset.py"
        )

    cases = load_cases(args.dataset)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    print(f"benchmark n={len(cases)} model={args.model} dataset={args.dataset.name}")
    rows: list[dict] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    t_wall0 = time.time()

    for i, case in enumerate(cases, 1):
        if i > 1 and args.sleep > 0:
            time.sleep(args.sleep)
        statement = case["statement"]
        urls = case.get("urls") or []
        exp = expected_score(case)
        payload = {
            "statement": statement,
            "model": args.model,
            "judge_runs": args.judge_runs,
            "discover_evidence": bool(args.discover_evidence) or not urls,
        }
        if urls:
            payload["urls"] = urls
            payload["discover_evidence"] = bool(args.discover_evidence)
        if case.get("claim_count") is not None:
            payload["claim_count"] = int(case["claim_count"])
        elif case.get("condition") == "mixed":
            payload["claim_count"] = 2

        t0 = time.time()
        try:
            resp = requests.post(API, json=payload, timeout=180)
            latency = round(time.time() - t0, 2)
            if resp.status_code != 200:
                print(f"[{i}/{len(cases)}] {case.get('id', i)} fail {resp.status_code}")
                rows.append(
                    {
                        "id": case.get("id"),
                        "topic": case.get("topic"),
                        "condition": case.get("condition"),
                        "pair_id": case.get("pair_id"),
                        "model": args.model,
                        "expected_score": exp,
                        "error": f"{resp.status_code}: {resp.text[:200]}",
                        "latency_seconds": latency,
                    }
                )
                continue
            body = resp.json()
            research = body.get("research") or {}
            row = {
                "id": case.get("id"),
                "topic": case.get("topic"),
                "condition": case.get("condition"),
                "pair_id": case.get("pair_id"),
                "prestige_bin": case.get("prestige_bin"),
                "model": args.model,
                "expected_score": exp,
                "groundedness_score": body.get("groundedness_score"),
                "authority_multiplier": body.get("authority_multiplier"),
                "trust_index": body.get("trust_index"),
                "evidence_quality": body.get("evidence_quality"),
                "evidence_mode": body.get("evidence_mode"),
                "discovery_weight": body.get("discovery_weight"),
                "inflation": research.get("inflation"),
                "research_source": research.get("source"),
                "judge_std": body.get("judge_std"),
                "latency_seconds": latency,
                "answer_chars": case.get("answer_chars") or len(statement),
                "urls": json.dumps(urls),
                "analyst_reasoning": (body.get("analyst_reasoning") or "").replace("\n", " | ")[
                    :1500
                ],
            }
            rows.append(row)
            print(
                f"[{i}/{len(cases)}] {case.get('id', i)}  "
                f"g={row['groundedness_score']}  exp={exp}  "
                f"{row['condition']}  {latency}s"
            )
        except Exception as exc:
            latency = round(time.time() - t0, 2)
            print(f"[{i}/{len(cases)}] {case.get('id', i)} fail {exc}")
            rows.append(
                {
                    "id": case.get("id"),
                    "condition": case.get("condition"),
                    "model": args.model,
                    "expected_score": exp,
                    "error": str(exc),
                    "latency_seconds": latency,
                }
            )

        pd.DataFrame(rows).to_csv(args.output, index=False)

    wall = round(time.time() - t_wall0, 2)
    summary = summarize(rows)
    summary["wall_seconds"] = wall
    summary["model"] = args.model
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(args.output, index=False)
    print(f"wrote {args.output}")
    print(f"summary -> {summary_path}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
