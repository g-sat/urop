from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import (
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

sns.set_theme(style="whitegrid")
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11})


def bin_score(v: float) -> str:
    if v <= 0.25:
        return "False"
    if v <= 0.75:
        return "Partial"
    return "True"


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"missing {CSV} — run scripts/run_benchmark.py first")

    RESULTS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV)
    df["expected_class"] = df["expected_score"].apply(bin_score)
    df["predicted_class"] = df["groundedness_score"].apply(bin_score)
    labels = ["False", "Partial", "True"]
    tradeoff: list[dict] = []

    with open(REPORT, "w", encoding="utf-8") as out:
        out.write("LinkGround metrics\n\n")
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

            f1 = f1_score(
                sub["expected_class"],
                sub["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )
            prec = precision_score(
                sub["expected_class"],
                sub["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )
            rec = recall_score(
                sub["expected_class"],
                sub["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )
            tradeoff.append({"model": str(model), "latency": latency, "mae": mae, "f1": f1})

            out.write(f"{model}\n")
            out.write(f"  latency={latency:.2f}s  mae={mae:.4f}  rmse={rmse:.4f}\n")
            out.write(f"  pearson={pr:.4f}  spearman={sr:.4f}\n")
            if "trust_index" in sub.columns:
                terr = sub["trust_index"] - sub["expected_score"]
                out.write(f"  trust_mae={float(np.abs(terr).mean()):.4f}\n")
            out.write(f"  f1={f1:.4f}  precision={prec:.4f}  recall={rec:.4f}\n")
            out.write(
                classification_report(
                    sub["expected_class"],
                    sub["predicted_class"],
                    labels=labels,
                    zero_division=0,
                )
            )
            out.write("\n")

            cm = confusion_matrix(sub["expected_class"], sub["predicted_class"], labels=labels)
            plt.figure(figsize=(6, 5))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels, cbar=False)
            plt.title(f"{model} (n={len(sub)})")
            plt.ylabel("expected")
            plt.xlabel("predicted")
            plt.tight_layout()
            path = RESULTS / f"confusion_matrix_{str(model).lower()}.png"
            plt.savefig(path, dpi=300)
            plt.close()
            print(path)

        tdf = pd.DataFrame(tradeoff)
        plt.figure(figsize=(7, 5))
        sns.scatterplot(data=tdf, x="latency", y="mae", hue="model", s=200)
        plt.xlabel("latency (s)")
        plt.ylabel("MAE")
        plt.tight_layout()
        mae_path = RESULTS / "latency_vs_mae.png"
        plt.savefig(mae_path, dpi=300)
        plt.close()
        print(mae_path)

        plt.figure(figsize=(7, 5))
        sns.scatterplot(data=tdf, x="latency", y="f1", hue="model", s=200)
        plt.xlabel("latency (s)")
        plt.ylabel("F1")
        plt.tight_layout()
        f1_path = RESULTS / "latency_vs_f1.png"
        plt.savefig(f1_path, dpi=300)
        plt.close()
        print(f1_path)

    print(REPORT)


if __name__ == "__main__":
    main()
