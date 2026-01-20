import matplotlib.pyplot as plt
import numpy as np

# === 1. 數據輸入 (Data Entry from -2.png files) ===
labels = ['Success (R0)', 'Success (R1)', 'Success (R2)', 'Success (R3)', 'Failure (R3)']

# d500 (CQI 3 - Run 2)
d500_means = [7617, 15751, 23698, 29606, 29619]

# d2000 (CQI 3 - Run 2)
d2000_means = [9042, 19541, 29853, 38824, 39281]

# 計算差異與百分比
diffs = np.array(d2000_means) - np.array(d500_means)
pct_changes = (diffs / np.array(d500_means)) * 100

# === 2. 繪圖設定 (Plot Configuration) ===
x = np.arange(len(labels))  # 標籤位置
width = 0.35  #長條寬度

fig, ax = plt.subplots(figsize=(14, 7))

# 繪製長條
rects1 = ax.bar(x - width/2, d500_means, width, label='d500 (CQI 3)', color='#5cb85c', alpha=0.9)
rects2 = ax.bar(x + width/2, d2000_means, width, label='d2000 (CQI 3)', color='#ff9800', alpha=0.9)

# 設定標題與軸標籤
ax.set_ylabel('Latency (us)', fontsize=12)
ax.set_title('HARQ Latency Comparison with % Growth: d500 vs d2000 (CQI 3)', fontsize=14, pad=20)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=11)
ax.legend(fontsize=11)
ax.grid(axis='y', linestyle='--', alpha=0.5)

# === 3. 數值與百分比標註函數 (Annotation Function) ===
def autolabel_with_diff(rects_base, rects_comp, percentages):
    """
    rects_base: d500 的長條 (基準)
    rects_comp: d2000 的長條 (比較對象)
    percentages: 計算出的百分比陣列
    """
    # 標示 d500 的數值
    for rect in rects_base:
        height = rect.get_height()
        ax.annotate(f'{int(height)}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, color='darkgreen')

    # 標示 d2000 的數值以及與 d500 的差異百分比
    for idx, rect in enumerate(rects_comp):
        height = rect.get_height()
        pct = percentages[idx]
        
        # 數值 (例如: 9042)
        ax.annotate(f'{int(height)}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='#d85c00')
        
        # 百分比差異 (例如: +18.7%) - 顯示在兩條柱子中間上方
        # 抓取兩柱中間的 X 座標
        center_x = x[idx]
        max_height = max(d500_means[idx], d2000_means[idx])
        
        ax.annotate(f'+{pct:.1f}%',
                    xy=(center_x, max_height),
                    xytext=(0, 20), textcoords="offset points", # 把百分比稍微拉高一點，避免擋到數值
                    ha='center', va='bottom', fontsize=11, fontweight='bold', color='red',
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", alpha=0.6))

# 執行標註
autolabel_with_diff(rects1, rects2, pct_changes)

# 自動調整佈局
fig.tight_layout()
fig.savefig('/home/hpe/ming-python/cqi3-compare-2.png', dpi=300, bbox_inches='tight')
plt.close(fig)