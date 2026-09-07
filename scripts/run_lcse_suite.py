from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "lcse"
API = "http://127.0.0.1:8000/v1/evaluate"
HEALTH = "http://127.0.0.1:8000/health"
SUITE_FILES = (
    DATA_DIR / "confound_grid.jsonl",
    DATA_DIR / "citation_swap.jsonl",
    DATA_DIR / "ethics_audit.jsonl",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_suite(paths: list[Path]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            cases.extend(load_jsonl(path))
    return cases


def score(api: str, case: dict[str, Any], model: str) -> dict[str, Any]:
    urls = case.get("urls") or []
    payload: dict[str, Any] = {
        "statement": case["statement"],
        "model": model,
        "judge_runs": 1,
        "discover_evidence": not urls,
        "discovery_depth": 0,
        "max_discovered_urls": 3,
    }
    if urls:
        payload["urls"] = urls
        payload["discover_evidence"] = False

    t0 = time.time()
    resp = requests.post(api, json=payload, timeout=180)
    latency = round(time.time() - t0, 2)
    if resp.status_code != 200:
        return {**case, "error": f"{resp.status_code}: {resp.text[:200]}", "latency_seconds": latency}

    body = resp.json()
    return {
        **case,
        "groundedness_score": body.get("groundedness_score"),
        "authority_multiplier": body.get("authority_multiplier"),
        "trust_index": body.get("trust_index"),
        "evidence_mode": body.get("evidence_mode"),
        "discovery_weight": body.get("discovery_weight"),
        "research": body.get("research", {}),
        "latency_seconds": latency,
    }


def _mean(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 3) if vals else None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if "error" not in r and isinstance(r.get("groundedness_score"), (int, float))]

    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pairs: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    flags: dict[str, int] = defaultdict(int)
    modes: dict[str, int] = defaultdict(int)

    for r in ok:
        if r.get("cell"):
            by_cell[str(r["cell"])].append(r)
        if r.get("pair_id") and r.get("condition"):
            pairs[str(r["pair_id"])][str(r["condition"])] = r
        modes[str(r.get("evidence_mode") or r.get("regime") or "?")] += 1
        for flag in (r.get("research") or {}).get("flags") or []:
            flags[str(flag)] += 1

    cells = {}
    for cell, items in by_cell.items():
        inflations = [float((x.get("research") or {}).get("inflation") or 0) for x in items]
        cells[cell] = {
            "n": len(items),
            "support": _mean([float(x["groundedness_score"]) for x in items]),
            "trust": _mean([float(x["trust_index"]) for x in items]),
            "inflation": _mean(inflations),
        }

    deltas = []
    swap_rows = []
    for pid, conds in pairs.items():
        m, s = conds.get("matched"), conds.get("swapped")
        if not m or not s:
            continue
        d = float(m["groundedness_score"]) - float(s["groundedness_score"])
        deltas.append(d)
        swap_rows.append(
            {
                "pair": pid,
                "matched": m["groundedness_score"],
                "swapped": s["groundedness_score"],
                "delta": round(d, 3),
            }
        )

    return {
        "n": len(rows),
        "scored": len(ok),
        "failed": len(rows) - len(ok),
        "mean_support": _mean([float(r["groundedness_score"]) for r in ok]),
        "mean_trust": _mean([float(r["trust_index"]) for r in ok]),
        "cells": cells,
        "citation_swaps": swap_rows,
        "mean_swap_delta": _mean(deltas),
        "evidence_modes": dict(modes),
        "flag_counts": dict(flags),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the eval suite against a local LinkGround API.")
    parser.add_argument("--model", default="llama3.1")
    parser.add_argument("--api-url", default=API)
    parser.add_argument("--health-url", default=HEALTH)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "lcse_suite.json")
    parser.add_argument(
        "--only",
        choices=["confound", "swaps", "ethics", "all"],
        default="all",
        help="Subset of suite files to run",
    )
    args = parser.parse_args()

    try:
        requests.get(args.health_url, timeout=5).raise_for_status()
    except Exception as exc:
        raise SystemExit(f"API down at {args.health_url}: {exc}") from exc

    file_map = {
        "confound": SUITE_FILES[0],
        "swaps": SUITE_FILES[1],
        "ethics": SUITE_FILES[2],
    }
    paths = list(SUITE_FILES) if args.only == "all" else [file_map[args.only]]
    cases = load_suite(paths)
    if not cases:
        raise SystemExit(f"No cases under {DATA_DIR}")

    print(f"scoring {len(cases)} cases")
    rows = []
    for i, case in enumerate(cases, 1):
        if i > 1:
            time.sleep(2.5)
        row = score(args.api_url, case, args.model)
        rows.append(row)
        cid = case.get("id", i)
        if "error" in row:
            print(f"[{i}/{len(cases)}] {cid} fail")
        else:
            print(
                f"[{i}/{len(cases)}] {cid}  "
                f"g={row['groundedness_score']}  "
                f"t={row['trust_index']}  "
                f"{row.get('evidence_mode')}"
            )

    summary = summarize(rows)
    report = {
        "model": args.model,
        "cases": rows,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"done -> {args.output}")
    print(
        f"scored={summary['scored']}  "
        f"mean_support={summary['mean_support']}  "
        f"mean_swap_delta={summary['mean_swap_delta']}"
    )


if __name__ == "__main__":
    main()
