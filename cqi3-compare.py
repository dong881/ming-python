import matplotlib.pyplot as plt
import numpy as np

# Data extracted from user images (CQI 3 Scenario)
labels = ['Success (R0)', 'Success (R1)', 'Success (R2)', 'Success (R3)']

# d500 (CQI 3) Data
d500_means = [7471, 14694, 22096, 29522]

# d2000 (CQI 3) Data
d2000_means = [8998, 18792, 28690, 39028]

# calculate percent differences relative to d500
percents = [ (b - a) / a * 100 for a, b in zip(d500_means, d2000_means) ]

x = np.arange(len(labels))  # the label locations
width = 0.35  # the width of the bars

fig, ax = plt.subplots(figsize=(12, 6))

# Plotting the bars
rects1 = ax.bar(x - width/2, d500_means, width, label='d500 (CQI 3)', color='#5cb85c', alpha=0.9)
rects2 = ax.bar(x + width/2, d2000_means, width, label='d2000 (CQI 3)', color='#f0ad4e', alpha=0.9)

# Add some text for labels, title and custom x-axis tick labels, etc.
ax.set_ylabel('Average Time (us)')
ax.set_title('HARQ Latency Comparison: d500 vs d2000 (CQI 3)')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.5)

# Add value labels on top of bars
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')

autolabel(rects1)
autolabel(rects2)

# Annotate percent differences above each group (relative to d500)
max_val = max(max(d500_means), max(d2000_means))
y_offset = max_val * 0.04  # small vertical offset
for i, p in enumerate(percents):
    ax.text(x[i], max(d500_means[i], d2000_means[i]) + y_offset, f'{p:+.1f}%', 
            ha='center', va='bottom', fontsize=10, fontweight='bold', color='black')

fig.tight_layout()

# Save figure to file instead of showing it
output_path = '/home/hpe/ming-python/compare2.png'
fig.savefig(output_path, dpi=300, bbox_inches='tight')
print(f'Saved figure to {output_path}')

# Also print percent differences to console
for label, p in zip(labels, percents):
    print(f'{label}: {p:+.1f}%')
