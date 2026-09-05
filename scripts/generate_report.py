"""
Generate academic metrics, confusion matrices, and latency/F1 trade-off plots
from LinkGround benchmark output.
"""

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
RESULTS_DIR = ROOT / "results"
METRICS_CSV = RESULTS_DIR / "benchmark_metrics.csv"
LEGACY_METRICS_CSV = RESULTS_DIR / "hardware_vs_accuracy_metrics.csv"
REPORT_PATH = RESULTS_DIR / "metrics_report.txt"

sns.set_theme(style="whitegrid")
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11})


def quantize_score(value: float) -> str:
    if value <= 0.25:
        return "False"
    if value <= 0.75:
        return "Partial"
    return "True"


def load_metrics() -> pd.DataFrame:
    path = METRICS_CSV if METRICS_CSV.exists() else LEGACY_METRICS_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"No metrics CSV found. Expected {METRICS_CSV} (run scripts/run_benchmark.py first)."
        )

    frame = pd.read_csv(path)

    # Support both new and legacy column names
    rename_map = {
        "Model_Engine": "model",
        "Statement": "statement",
        "Actual_Truth": "expected_score",
        "Predicted_Truth": "groundedness_score",
        "Authority_Multiplier": "authority_multiplier",
        "Final_Trust_Index": "trust_index",
        "Latency_Seconds": "latency_seconds",
        "Academic_Reasoning": "analyst_reasoning",
    }
    frame = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
    return frame


def generate_report() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_metrics()

    frame["expected_class"] = frame["expected_score"].apply(quantize_score)
    frame["predicted_class"] = frame["groundedness_score"].apply(quantize_score)
    labels = ["False", "Partial", "True"]
    tradeoff_rows: list[dict] = []

    with open(REPORT_PATH, "w", encoding="utf-8") as report:
        report.write("LinkGround Evaluation Report\n")
        report.write("=" * 72 + "\n")
        report.write(
            "PRIMARY metrics use continuous groundedness (e.g. 0.77 vs GT 1.0 → error 0.23).\n"
            "SECONDARY ternary labels (False/Partial/True) are only for classification views;\n"
            "they do not replace MAE/RMSE/correlation.\n"
        )
        report.write("=" * 72 + "\n\n")

        for model_name in frame["model"].unique():
            subset = frame[frame["model"] == model_name]
            latency = subset["latency_seconds"].mean()
            errors = subset["groundedness_score"] - subset["expected_score"]
            mae = float(np.abs(errors).mean())
            rmse = float(np.sqrt((errors**2).mean()))

            if len(subset) >= 3 and subset["groundedness_score"].nunique() > 1:
                pearson_r, _ = pearsonr(subset["expected_score"], subset["groundedness_score"])
                spearman_r, _ = spearmanr(subset["expected_score"], subset["groundedness_score"])
            else:
                pearson_r = float("nan")
                spearman_r = float("nan")

            f1 = f1_score(
                subset["expected_class"],
                subset["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )
            precision = precision_score(
                subset["expected_class"],
                subset["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )
            recall = recall_score(
                subset["expected_class"],
                subset["predicted_class"],
                average="weighted",
                labels=labels,
                zero_division=0,
            )

            tradeoff_rows.append(
                {
                    "model": str(model_name).upper(),
                    "latency": latency,
                    "mae": mae,
                    "f1_weighted": f1,
                }
            )

            report.write(f"Model: {str(model_name).upper()}\n")
            report.write("-" * 40 + "\n")
            report.write(f"Mean latency (s)                      : {latency:.2f}\n")
            report.write("\n[PRIMARY — continuous groundedness]\n")
            report.write(f"Groundedness MAE                      : {mae:.4f}\n")
            report.write(f"Groundedness RMSE                     : {rmse:.4f}\n")
            report.write(f"Pearson r                             : {pearson_r:.4f}\n")
            report.write(f"Spearman rho                          : {spearman_r:.4f}\n")

            if "trust_index" in subset.columns:
                trust_errors = subset["trust_index"] - subset["expected_score"]
                report.write(
                    f"Trust-index MAE                        : {float(np.abs(trust_errors).mean()):.4f}\n"
                )
                report.write(
                    f"Trust-index RMSE                       : {float(np.sqrt((trust_errors**2).mean())):.4f}\n"
                )
            if "authority_multiplier" in subset.columns:
                report.write(
                    f"Mean link authority                    : {subset['authority_multiplier'].mean():.4f}\n"
                )

            report.write("\n[SECONDARY — ternary bins for classification only]\n")
            report.write(f"Precision (weighted)                  : {precision:.4f}\n")
            report.write(f"Recall (weighted)                     : {recall:.4f}\n")
            report.write(f"F1 (weighted)                         : {f1:.4f}\n\n")
            report.write("Classification report:\n")
            report.write(
                classification_report(
                    subset["expected_class"],
                    subset["predicted_class"],
                    labels=labels,
                    zero_division=0,
                )
            )
            report.write("\n" + "=" * 72 + "\n\n")

            matrix = confusion_matrix(
                subset["expected_class"],
                subset["predicted_class"],
                labels=labels,
            )
            plt.figure(figsize=(6, 5))
            sns.heatmap(
                matrix,
                annot=True,
                fmt="d",
                cmap="Blues",
                xticklabels=labels,
                yticklabels=labels,
                cbar=False,
            )
            plt.title(f"Confusion Matrix: {str(model_name).upper()} (n={len(subset)})")
            plt.ylabel("Expected")
            plt.xlabel("Predicted")
            plt.tight_layout()
            matrix_path = RESULTS_DIR / f"confusion_matrix_{str(model_name).lower()}.png"
            plt.savefig(matrix_path, dpi=300)
            plt.close()
            print(f"[report] wrote {matrix_path}")

        tradeoff = pd.DataFrame(tradeoff_rows)

        # Primary trade-off: latency vs continuous MAE (lower MAE is better)
        plt.figure(figsize=(7, 5))
        sns.scatterplot(
            data=tradeoff,
            x="latency",
            y="mae",
            hue="model",
            style="model",
            s=280,
            palette="Set1",
        )
        for _, row in tradeoff.iterrows():
            plt.text(
                row["latency"] + 0.05,
                row["mae"],
                f"{row['model']} (MAE={row['mae']:.3f})",
                fontsize=9,
            )
        plt.title("Primary Trade-off: Latency vs Continuous Groundedness MAE")
        plt.xlabel("Mean latency (seconds)")
        plt.ylabel("Groundedness MAE (lower is better)")
        plt.ylim(bottom=-0.02)
        plt.xlim(left=0)
        plt.tight_layout()
        mae_scatter = RESULTS_DIR / "latency_vs_mae.png"
        plt.savefig(mae_scatter, dpi=300)
        plt.close()
        print(f"[report] wrote {mae_scatter}")

        # Secondary trade-off: latency vs ternary F1
        plt.figure(figsize=(7, 5))
        sns.scatterplot(
            data=tradeoff,
            x="latency",
            y="f1_weighted",
            hue="model",
            style="model",
            s=280,
            palette="Set1",
        )
        for _, row in tradeoff.iterrows():
            plt.text(
                row["latency"] + 0.05,
                row["f1_weighted"] - 0.002,
                f"{row['model']} (F1={row['f1_weighted']:.2%})",
                fontsize=9,
            )
        plt.title("Secondary Trade-off: Latency vs Weighted F1 (ternary bins)")
        plt.xlabel("Mean latency (seconds)")
        plt.ylabel("Weighted F1")
        plt.ylim(-0.05, 1.05)
        plt.xlim(left=0)
        plt.tight_layout()
        scatter_path = RESULTS_DIR / "latency_vs_f1.png"
        plt.savefig(scatter_path, dpi=300)
        plt.close()
        print(f"[report] wrote {scatter_path}")

    print(f"[report] wrote {REPORT_PATH}")


if __name__ == "__main__":
    generate_report()
