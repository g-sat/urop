import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")

def plot_urop_metrics():
    try:
        df = pd.read_csv("urop_benchmark_metrics.csv")
    except FileNotFoundError:
        print("❌ Error: 'urop_benchmark_metrics.csv' not found. Run benchmark.py first.")
        return

    df['Short_Text'] = df['Statement'].apply(lambda x: x[:25] + "...")

    # Chart 1: Latency Bar Plot
    plt.figure(figsize=(9, 4.5))
    sns.barplot(x='Short_Text', y='Latency', data=df, palette='magma', hue='Short_Text', legend=False)
    plt.axhline(df['Latency'].mean(), color='crimson', linestyle='--', label=f"Mean Latency ({df['Latency'].mean():.2f}s)")
    plt.title("API Computing Latency Metrics", fontsize=12, fontweight='bold')
    plt.ylabel("Processing Time (Seconds)")
    plt.xlabel("Tested Claims")
    plt.xticks(rotation=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig("metric_latency_graph.png", dpi=300)
    plt.close()
    print("📉 Graphical report exported: 'metric_latency_graph.png'")

    # Chart 2: Accuracy Pie Plot
    plt.figure(figsize=(5, 5))
    raw_list = df['Correct'].tolist()
    plt.pie(
        [raw_list.count(True), raw_list.count(False)],
        labels=['Aligned True', 'Mismatched False'],
        colors=['#2ecc71', '#e74c3c'],
        autopct='%1.1f%%',
        startangle=120
    )
    plt.title("Local Judge Accuracy Metrics", fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.savefig("metric_accuracy_graph.png", dpi=300)
    plt.close()
    print("🍕 Graphical report exported: 'metric_accuracy_graph.png'")

if __name__ == "__main__":
    plot_urop_metrics()
