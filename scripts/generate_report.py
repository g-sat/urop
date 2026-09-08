"""Generate paper-facing metrics from results/benchmark_metrics.csv.

Primary report: MAE by condition + citation-swap Δ.
Secondary: overall MAE/correlation + ternary accuracy/precision/recall/F1.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
CSV = RESULTS / "benchmark_metrics.csv"
REPORT = RESULTS / "metrics_report.txt"
SUMMARY = RESULTS / "benchmark_metrics.summary.json"

TERNARY_LABELS = ["False", "Partial", "True"]

sns.set_theme(style="whitegrid")
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11})


def bin_score(v: float) -> str:
    if v <= 0.25:
        return "False"
    if v <= 0.75:
        return "Partial"
    return "True"


def safe_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", str(model))[:80]


def swap_deltas(sub: pd.DataFrame) -> list[float]:
    deltas: list[float] = []
    if "pair_id" not in sub.columns or "condition" not in sub.columns:
        return deltas
    for pid, grp in sub.groupby("pair_id"):
        if pd.isna(pid):
            continue
        matched = grp[grp["condition"].isin(["supported", "matched"])]
        swapped = grp[grp["condition"] == "swapped"]
        if len(matched) and len(swapped):
            deltas.append(
                float(matched["groundedness_score"].iloc[0])
                - float(swapped["groundedness_score"].iloc[0])
            )
    return deltas


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"missing {CSV} — run scripts/run_benchmark.py first")

    RESULTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV)
    df = df[df["groundedness_score"].notna()].copy()
    if df.empty:
        raise SystemExit("no scored rows in benchmark_metrics.csv")

    df["expected_class"] = df["expected_score"].apply(bin_score)
    df["predicted_class"] = df["groundedness_score"].apply(bin_score)

    summary_payload: dict = {"models": {}}
    tradeoff: list[dict] = []

    with open(REPORT, "w", encoding="utf-8") as out:
        out.write("LinkGround paper benchmark metrics\n")
        out.write("PRIMARY: MAE by condition + citation-swap delta (supported - swapped)\n")
        out.write("Secondary: overall MAE/RMSE/correlation + ternary accuracy/precision/F1\n\n")

        for model in df["model"].unique():
            sub = df[df["model"] == model]
            err = sub["groundedness_score"] - sub["expected_score"]
            mae = float(np.abs(err).mean())
            rmse = float(np.sqrt((err**2).mean()))
            latency = float(sub["latency_seconds"].mean())

            if len(sub) >= 3 and sub["groundedness_score"].nunique() > 1:
                pr, _ = pearsonr(sub["expected_score"], sub["groundedness_score"])
                sr, _ = spearmanr(sub["expected_score"], sub["groundedness_score"])
            else:
                pr = sr = float("nan")

            deltas = swap_deltas(sub)
            mean_delta = float(sum(deltas) / len(deltas)) if deltas else float("nan")

            y_true = sub["expected_class"]
            y_pred = sub["predicted_class"]
            acc = float(accuracy_score(y_true, y_pred))
            prec = float(
                precision_score(
                    y_true, y_pred, average="weighted", labels=TERNARY_LABELS, zero_division=0
                )
            )
            rec = float(
                recall_score(
                    y_true, y_pred, average="weighted", labels=TERNARY_LABELS, zero_division=0
                )
            )
            f1w = float(
                f1_score(
                    y_true, y_pred, average="weighted", labels=TERNARY_LABELS, zero_division=0
                )
            )
            f1m = float(
                f1_score(y_true, y_pred, average="macro", labels=TERNARY_LABELS, zero_division=0)
            )

            tradeoff.append(
                {
                    "model": str(model),
                    "latency": latency,
                    "mae": mae,
                    "swap_delta": mean_delta,
                    "f1": f1w,
                }
            )

            out.write(f"{model}\n")
            out.write(f"  n={len(sub)}  latency={latency:.2f}s\n")
            out.write(f"  overall_mae={mae:.4f}  rmse={rmse:.4f}  (secondary)\n")
            out.write(f"  pearson={pr:.4f}  spearman={sr:.4f}\n")

            cond_rows: dict[str, dict] = {}
            if "condition" in sub.columns:
                out.write("  MAE by condition (PRIMARY):\n")
                for cond, grp in sorted(sub.groupby("condition"), key=lambda x: str(x[0])):
                    cerr = grp["groundedness_score"] - grp["expected_score"]
                    cmae = float(np.abs(cerr).mean())
                    out.write(
                        f"    {cond}: n={len(grp)} mae={cmae:.4f} "
                        f"mean_g={grp['groundedness_score'].mean():.3f} "
                        f"mean_exp={grp['expected_score'].mean():.3f}\n"
                    )
                    cond_rows[str(cond)] = {
                        "n": int(len(grp)),
                        "mae": cmae,
                        "mean_groundedness": float(grp["groundedness_score"].mean()),
                        "mean_expected": float(grp["expected_score"].mean()),
                    }

            if deltas:
                out.write(
                    f"  citation_swap delta (PRIMARY): pairs={len(deltas)}  "
                    f"mean_delta={mean_delta:.3f}  "
                    f"min={min(deltas):.3f}  max={max(deltas):.3f}\n"
                )
            else:
                out.write("  citation_swap delta: (no supported/swapped pairs)\n")

            if "trust_index" in sub.columns:
                terr = sub["trust_index"] - sub["expected_score"]
                out.write(f"  trust_mae={float(np.abs(terr).mean()):.4f}\n")
            if "inflation" in sub.columns and sub["inflation"].notna().any():
                out.write(f"  mean_inflation={float(sub['inflation'].dropna().mean()):.4f}\n")

            out.write(
                "  ternary classification (SECONDARY; bins: False<=0.25, Partial<=0.75, True):\n"
            )
            out.write(
                f"    accuracy={acc:.4f}  precision={prec:.4f}  "
                f"recall={rec:.4f}  f1_weighted={f1w:.4f}  f1_macro={f1m:.4f}\n"
            )
            if "condition" in sub.columns:
                out.write("    by condition (accuracy / f1_weighted):\n")
                for cond, grp in sorted(sub.groupby("condition"), key=lambda x: str(x[0])):
                    yy, pp = grp["expected_class"], grp["predicted_class"]
                    c_acc = float(accuracy_score(yy, pp))
                    c_f1 = float(
                        f1_score(
                            yy, pp, average="weighted", labels=TERNARY_LABELS, zero_division=0
                        )
                    )
                    out.write(f"      {cond}: acc={c_acc:.3f}  f1w={c_f1:.3f}\n")
            out.write(
                classification_report(
                    y_true, y_pred, labels=TERNARY_LABELS, zero_division=0, digits=4
                )
            )
            out.write("\n")

            summary_payload["models"][str(model)] = {
                "n": int(len(sub)),
                "latency": latency,
                "overall_mae": mae,
                "rmse": rmse,
                "pearson": None if np.isnan(pr) else float(pr),
                "spearman": None if np.isnan(sr) else float(sr),
                "mae_by_condition": cond_rows,
                "swap_delta_mean": None if np.isnan(mean_delta) else mean_delta,
                "swap_delta_min": min(deltas) if deltas else None,
                "swap_delta_max": max(deltas) if deltas else None,
                "swap_pairs": len(deltas),
                "ternary": {
                    "accuracy": acc,
                    "precision_weighted": prec,
                    "recall_weighted": rec,
                    "f1_weighted": f1w,
                    "f1_macro": f1m,
                },
            }

            if cond_rows:
                conds = list(cond_rows.keys())
                maes = [cond_rows[c]["mae"] for c in conds]
                plt.figure(figsize=(8, 4.5))
                sns.barplot(x=conds, y=maes, color="#4C78A8")
                plt.ylabel("MAE")
                plt.xlabel("condition")
                plt.title(f"{model}: MAE by condition")
                plt.xticks(rotation=20, ha="right")
                plt.tight_layout()
                path = RESULTS / f"mae_by_condition_{safe_name(model)}.png"
                plt.savefig(path, dpi=300)
                plt.close()
                print(path)

            if deltas:
                plt.figure(figsize=(6, 4))
                sns.histplot(deltas, bins=min(10, max(3, len(deltas))), kde=False, color="#F58518")
                plt.axvline(mean_delta, color="black", linestyle="--", label=f"mean={mean_delta:.3f}")
                plt.xlabel("supported − swapped groundedness")
                plt.ylabel("pairs")
                plt.title(f"{model}: citation-swap Δ")
                plt.legend()
                plt.tight_layout()
                path = RESULTS / f"swap_delta_{safe_name(model)}.png"
                plt.savefig(path, dpi=300)
                plt.close()
                print(path)

            cm = confusion_matrix(y_true, y_pred, labels=TERNARY_LABELS)
            plt.figure(figsize=(6, 5))
            sns.heatmap(
                cm,
                annot=True,
                fmt="d",
                cmap="Blues",
                xticklabels=TERNARY_LABELS,
                yticklabels=TERNARY_LABELS,
                cbar=False,
            )
            plt.title(f"{model} ternary (n={len(sub)})")
            plt.ylabel("expected")
            plt.xlabel("predicted")
            plt.tight_layout()
            cm_path = RESULTS / f"confusion_matrix_{safe_name(model)}.png"
            plt.savefig(cm_path, dpi=300)
            plt.close()
            print(cm_path)

        if "condition" in df.columns:
            plt.figure(figsize=(8, 5))
            sns.boxplot(data=df, x="condition", y="groundedness_score")
            plt.xticks(rotation=20, ha="right")
            plt.ylabel("groundedness")
            plt.tight_layout()
            cond_path = RESULTS / "groundedness_by_condition.png"
            plt.savefig(cond_path, dpi=300)
            plt.close()
            print(cond_path)

        tdf = pd.DataFrame(tradeoff)
        if len(tdf):
            plt.figure(figsize=(7, 5))
            sns.scatterplot(data=tdf, x="latency", y="mae", hue="model", s=200)
            plt.xlabel("latency (s)")
            plt.ylabel("overall MAE (secondary)")
            plt.tight_layout()
            mae_path = RESULTS / "latency_vs_mae.png"
            plt.savefig(mae_path, dpi=300)
            plt.close()
            print(mae_path)

            if tdf["swap_delta"].notna().any():
                plt.figure(figsize=(7, 5))
                sns.scatterplot(data=tdf, x="latency", y="swap_delta", hue="model", s=200)
                plt.xlabel("latency (s)")
                plt.ylabel("mean swap Δ (supported − swapped)")
                plt.tight_layout()
                delta_path = RESULTS / "latency_vs_swap_delta.png"
                plt.savefig(delta_path, dpi=300)
                plt.close()
                print(delta_path)

            plt.figure(figsize=(7, 5))
            sns.scatterplot(data=tdf, x="latency", y="f1", hue="model", s=200)
            plt.xlabel("latency (s)")
            plt.ylabel("F1 weighted (ternary, secondary)")
            plt.tight_layout()
            f1_path = RESULTS / "latency_vs_f1.png"
            plt.savefig(f1_path, dpi=300)
            plt.close()
            print(f1_path)

    SUMMARY.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(SUMMARY)
    print(REPORT)


if __name__ == "__main__":
    main()
