import os
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"

# Set unified academic styling parameters
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.family': 'sans-serif', 'font.size': 11})

def compile_urop_journal_metrics():
    metrics_csv_path = RESULTS_DIR / "hardware_vs_accuracy_metrics.csv"
    output_report_path = RESULTS_DIR / "final_academic_metrics_report.txt"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        df = pd.read_csv(metrics_csv_path)
    except FileNotFoundError:
        # Fallback for older runs that wrote into src/
        legacy = ROOT / "src" / "hardware_vs_accuracy_metrics.csv"
        try:
            df = pd.read_csv(legacy)
            print(f"⚠️ Using legacy metrics path: {legacy}")
        except FileNotFoundError:
            print(f"❌ Error: '{metrics_csv_path}' not found. Run builders/run_benchmark.py first!")
            return

    # 1. QUANTIZATION SCHEME FOR TRADITIONAL METRICS
    # This maps continuous decimals cleanly into three logical categorical bins
    def quantize_to_bins(val):
        if val <= 0.25:
            return "False"
        elif val <= 0.75:
            return "Partial"
        return "True"

    df['Actual_Class'] = df['Actual_Truth'].apply(quantize_to_bins)
    df['Predicted_Class'] = df['Predicted_Truth'].apply(quantize_to_bins)
    
    labels_order = ["False", "Partial", "True"]
    unique_models = df['Model_Engine'].unique()
    
    # Open the text file where all numerical stats will be permanently saved
    with open(output_report_path, "w", encoding="utf-8") as report_file:
        report_file.write("========================================================================\n")
        report_file.write("🏆 UROP CONTINUOUS & CATEGORICAL PERFORMANCE telemetry MATRIX\n")
        report_file.write("========================================================================\n\n")
        
        # --- GRAPH 1 SETUP: PREPARE HARDWARE ACCURACY TRADE-OFF SCATTER ---
        tradeoff_records = []

        for model in unique_models:
            sub_df = df[df['Model_Engine'] == model]
            mean_latency = sub_df['Latency_Seconds'].mean()
            
            # Continuous Distance Error Calculations
            errors = sub_df['Predicted_Truth'] - sub_df['Actual_Truth']
            mae = np.abs(errors).mean()
            rmse = np.sqrt((errors ** 2).mean())

            # Rank/linear correlation — meaningful once predictions are continuous
            if len(sub_df) >= 3 and sub_df['Predicted_Truth'].nunique() > 1:
                pearson_r, _ = pearsonr(sub_df['Actual_Truth'], sub_df['Predicted_Truth'])
                spearman_r, _ = spearmanr(sub_df['Actual_Truth'], sub_df['Predicted_Truth'])
            else:
                pearson_r, spearman_r = float("nan"), float("nan")
            
            # Categorical Group Performance Indices (Weighted to account for bin sizes)
            f1 = f1_score(sub_df['Actual_Class'], sub_df['Predicted_Class'], average='weighted', labels=labels_order)
            precision = precision_score(sub_df['Actual_Class'], sub_df['Predicted_Class'], average='weighted', labels=labels_order, zero_division=0)
            recall = recall_score(sub_df['Actual_Class'], sub_df['Predicted_Class'], average='weighted', labels=labels_order, zero_division=0)
            
            # Append statistical averages for chart compilation
            tradeoff_records.append({
                "Model": model.upper(),
                "Latency": mean_latency,
                "F1_Weighted": f1
            })
            
            # Format and write strict data blocks into your text files
            report_file.write(f"🤖 ENGINE LOG ENCLAVE: {model.upper()}\n")
            report_file.write("-" * 40 + "\n")
            report_file.write(f"⏱️ Mean Processing Latency : {mean_latency:.2f} seconds\n")
            report_file.write(f"📉 Mean Absolute Error (MAE): {mae:.4f} (Continuous Deviation)\n")
            report_file.write(f"🎛️ Root Mean Squared Error : {rmse:.4f}\n")
            report_file.write(f"📈 Pearson r (continuous)  : {pearson_r:.4f}\n")
            report_file.write(f"📈 Spearman ρ (continuous) : {spearman_r:.4f}\n")

            # Dual-score reporting: groundedness (truth vs links) + authority-weighted trust
            if "Final_Trust_Index" in sub_df.columns:
                trust_err = sub_df["Final_Trust_Index"] - sub_df["Actual_Truth"]
                trust_mae = np.abs(trust_err).mean()
                trust_rmse = np.sqrt((trust_err ** 2).mean())
                report_file.write(f"🛡️ Trust-Index MAE         : {trust_mae:.4f}\n")
                report_file.write(f"🛡️ Trust-Index RMSE        : {trust_rmse:.4f}\n")
                if "Authority_Multiplier" in sub_df.columns:
                    report_file.write(
                        f"🔗 Mean Link Authority     : {sub_df['Authority_Multiplier'].mean():.4f}\n"
                    )

            report_file.write(f"🎯 Precision (Weighted)     : {precision:.4f}\n")
            report_file.write(f"🔄 Recall (Weighted)        : {recall:.4f}\n")
            report_file.write(f"📊 F1-Score (Weighted)      : {f1:.4f}\n\n")
            report_file.write("📋 Detailed Classification Matrix Report:\n")
            report_file.write(classification_report(sub_df['Actual_Class'], sub_df['Predicted_Class'], labels=labels_order, zero_division=0))
            report_file.write("\n" + "="*80 + "\n\n")
            
            # --- GRAPH 2 SETUP: INDIVIDUAL MODEL 3x3 CONFUSION MATRICES ---
            cm = confusion_matrix(sub_df['Actual_Class'], sub_df['Predicted_Class'], labels=labels_order)
            
            plt.figure(figsize=(6, 5))
            sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels_order, yticklabels=labels_order, 
                        cbar=False, annot_kws={"size": 14, "weight": "bold"})
            plt.title(f"Confusion Matrix Grid: {model.upper()} (N={len(sub_df)})", fontsize=12, fontweight='bold', pad=12)
            plt.ylabel("Actual Ground Truth Spec", fontsize=10, fontweight='bold')
            plt.xlabel("Model Predicted Alignment Spec", fontsize=10, fontweight='bold')
            plt.tight_layout()
            
            cm_filename = RESULTS_DIR / f"urop_confusion_matrix_{model.lower()}.png"
            plt.savefig(cm_filename, dpi=300)
            plt.close()
            print(f"📊 Matrix Heatmap plot file rendered and saved: '{cm_filename}'")

        # --- GENERATE GRAPH 3: SYSTEM TRADE-OFF ANALYSIS SCATTER PLOT ---
        tradeoff_df = pd.DataFrame(tradeoff_records)
        plt.figure(figsize=(7, 5))
        
        sns.scatterplot(
            x="Latency", 
            y="F1_Weighted", 
            hue="Model", 
            style="Model",
            data=tradeoff_df, 
            s=300, 
            palette="Set1",
            legend='full'
        )
        
        # Add labels dynamically next to the scatter plots on the canvas layout
        for _, row in tradeoff_df.iterrows():
            plt.text(
                x=row["Latency"] + 0.05, 
                y=row["F1_Weighted"] - 0.002, 
                s=f"{row['Model']} (F1: {row['F1_Weighted']:.2%})", 
                fontweight='bold', 
                fontsize=9
            )
            
        plt.title("UROP Systems Trade-Off: Local Latency vs. Weighted F1 Score", fontsize=11, fontweight='bold', pad=15)
        plt.xlabel("Mean Evaluation Processing Latency (Seconds)", fontsize=10, fontweight='bold')
        plt.ylabel("Quantized Macro-Weighted F1 Accuracy Score", fontsize=10, fontweight='bold')
        plt.ylim(-0.05, 1.05)
        plt.xlim(left=0)
        plt.tight_layout()
        
        scatter_filename = RESULTS_DIR / "hardware_vs_accuracy_scatter.png"
        plt.savefig(scatter_filename, dpi=300)
        plt.close()
        print(f"📈 Combined Trade-off scatter diagram rendered and saved: '{scatter_filename}'")
        
    print(f"\n🎉 Evaluation Loop Complete! Data metrics safely saved to '{output_report_path}'")

if __name__ == "__main__":
    compile_urop_journal_metrics()
