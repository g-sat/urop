import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set a clean academic style for the charts
sns.set_theme(style="whitegrid")

def generate_urop_visualizations():
    # 1. Load the benchmark results file
    try:
        df = pd.read_csv("evaluation_benchmark_results.csv")
    except FileNotFoundError:
        print("❌ Error: 'evaluation_benchmark_results.csv' not found. Run benchmark.py first!")
        return

    # Create a truncated label for the graph x-axis so it doesn't overlap
    df['Short_Statement'] = df['Statement'].apply(lambda x: x[:30] + "...")

    # --- GRAPH 1: LATENCY PERFORMANCE BAR CHART ---
    plt.figure(figsize=(10, 5))
    bar_plot = sns.barplot(
        x='Short_Statement', 
        y='Latency (seconds)', 
        data=df, 
        palette='viridis',
        hue='Short_Statement',
        legend=False
    )
    
    # Draw a line representing your overall latency average
    avg_latency = df['Latency (seconds)'].mean()
    plt.axhline(avg_latency, color='red', linestyle='--', linewidth=1.5, label=f'Avg Latency ({avg_latency:.2f}s)')
    
    plt.title("LLM Evaluation Execution Latency Per Test Case", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Input Statement Evaluated", fontsize=11, labelpad=10)
    plt.ylabel("Processing Time (Seconds)", fontsize=11)
    plt.xticks(rotation=15, ha='right')
    plt.legend(loc="upper right")
    plt.tight_layout()
    
    # Save chart image to workspace
    plt.savefig("latency_analysis.png", dpi=300)
    print("📈 Saved 'latency_analysis.png'")
    plt.close()

    # --- GRAPH 2: JUDGMENT ACCURACY PIE CHART ---
    plt.figure(figsize=(6, 6))
    
    # Safely convert column to a Python list and count occurrences manually
    # This completely bypasses the Pandas boolean indexing bug
    judgments_list = df['Is Judgment Correct'].tolist()
    correct_count = judgments_list.count(True)
    incorrect_count = judgments_list.count(False)

    plt.pie(
        [correct_count, incorrect_count], 
        labels=['Correct Judgment', 'Incorrect/Failed'], 
        colors=['#4CAF50', '#FF5722'], 
        autopct='%1.1f%%', 
        startangle=140,
        textprops={'fontweight': 'bold', 'fontsize': 12}
    )
    
    plt.title("Local Judge Accuracy Alignment Baseline", fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    
    # Save chart image to workspace
    plt.savefig("accuracy_alignment.png", dpi=300)
    print("🍕 Saved 'accuracy_alignment.png'")
    plt.close()
    
    print("\n🎉 Visual data tracking analysis completed successfully!")

if __name__ == "__main__":
    generate_urop_visualizations()
