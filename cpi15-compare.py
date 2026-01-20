import matplotlib.pyplot as plt
import numpy as np

# Data extracted from user images
labels = ['Success (R0)', 'Success (R1)', 'Success (R2)', 'Success (R3)', 'Failure (R3)']
d500_means = [7826, 15491, 23499, 32176, 33111]
d2000_means = [8983, 20166, 30431, 40566, 40545]

x = np.arange(len(labels))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots(figsize=(12, 6))
rects1 = ax.bar(x - width/2, d500_means, width, label='d500 (CQI 15)', color='#5cb85c', alpha=0.9)
rects2 = ax.bar(x + width/2, d2000_means, width, label='d2000 (CQI 15)', color='#f0ad4e', alpha=0.9)

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Average Time (us)')
ax.set_title('HARQ Latency Comparison: d500 vs d2000')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.5)

# Add value labels
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

autolabel(rects1)
autolabel(rects2)

# Calculate percentage differences and display them above each pair
percent_diffs = []
for a, b in zip(d500_means, d2000_means):
    if a == 0:
        pct = float('inf')  # or handle differently if you prefer
    else:
        pct = (b - a) / a * 100.0
    percent_diffs.append(pct)

# Annotate percent differences between the paired bars
for i, pct in enumerate(percent_diffs):
    y = max(d500_means[i], d2000_means[i])
    y_text = y + (max(d500_means + d2000_means) * 0.03)  # small offset relative to max height
    sign = '+' if pct >= 0 and np.isfinite(pct) else ''
    pct_text = f'{sign}{pct:.1f}%' if np.isfinite(pct) else 'inf'
    ax.annotate(pct_text,
                xy=(x[i], y_text),
                xytext=(0, 0),
                textcoords='offset points',
                ha='center', va='bottom', fontsize=10, fontweight='bold', color='blue')

fig.tight_layout()

# Save the figure to a file instead of showing it
output_path = '/home/hpe/ming-python/harq_latency_comparison.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight')
# plt.close(fig)  # uncomment if running in batch to free memory
