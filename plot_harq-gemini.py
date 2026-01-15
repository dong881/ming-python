import pandas as pd
import matplotlib.pyplot as plt
import re
import os
import sys

# ==========================================
# 核心分析函式
# ==========================================
def analyze_harq_log_final(filename):
    data = []
    
    # 正則表達式設計：
    # 1. 抓取狀態 (HARQ_SUCCESS 或 HARQ_FAILURE) -> group(1)
    # 2. 抓取 round 數值 -> group(2)
    # 3. 抓取 elapsed_us 數值 -> group(3)
    # 使用 non-greedy match (.*?) 確保能正確對應到同一行內的數值
    pattern = re.compile(r"(HARQ_SUCCESS|HARQ_FAILURE).*?round=(\d+).*?elapsed_us=(\d+)")
    
    print(f"正在分析檔案: {filename} ...")
    
    try:
        with open(filename, "r") as f:
            for line_num, line in enumerate(f):
                match = pattern.search(line)
                if match:
                    status = match.group(1)
                    r = int(match.group(2))
                    e = int(match.group(3))
                    
                    # 建立分類標籤
                    if "SUCCESS" in status:
                        cat = f"Success (R{r})"
                        is_failure = False
                    else:
                        cat = f"Failure (R{r})"
                        is_failure = True
                        
                    data.append({
                        "index": line_num,
                        "status": status,
                        "round": r,
                        "elapsed_us": e,
                        "category": cat,
                        "is_failure": is_failure
                    })
    except PermissionError:
        print(f"權限錯誤: 無法讀取檔案 {filename}。請確認您有讀取權限 (或是使用 sudo)。")
        return
    except FileNotFoundError:
        print(f"錯誤: 找不到檔案 {filename}")
        return

    if not data:
        print("警告: 檔案中找不到符合格式的數據。")
        print("請確認 Log 內容包含 'HARQ_SUCCESS' 或 'HARQ_FAILURE'，以及 'round=' 和 'elapsed_us='")
        return

    df = pd.DataFrame(data)

    # --- 1. 文字統計報告 ---
    # 依照 (是否失敗, Round, 分類名稱) 分組統計
    summary = df.groupby(["is_failure", "round", "category"])["elapsed_us"].describe()
    
    print("\n" + "="*40)
    print("      HARQ 效能分析報告      ")
    print("="*40)
    # 顯示 count, mean, min, max，並格式化小數點
    print(summary[['count', 'mean', 'min', 'max']].round(2))
    
    total_pkts = len(df)
    fail_pkts = len(df[df['is_failure'] == True])
    fail_rate = (fail_pkts / total_pkts * 100) if total_pkts > 0 else 0
    
    print("-" * 40)
    print(f"總封包數樣本: {total_pkts}")
    print(f"失敗封包數 (Failure): {fail_pkts}")
    print(f"封包遺失率 (BLER estimate): {fail_rate:.2f}%")
    print(f"整體平均耗時: {df['elapsed_us'].mean():.2f} us")
    print("="*40 + "\n")

    # ==========================================
    # 2. 視覺化繪圖
    # ==========================================
    plt.figure(figsize=(14, 12))
    plt.rcParams.update({'font.size': 11})

    # 排序邏輯：先排 Success R0-R3，最後排 Failure
    categories = sorted(df['category'].unique(), key=lambda x: (x.startswith("Failure"), x))
    
    # 定義顏色映射
    color_map = {}
    for cat in categories:
        if "Failure" in cat:
            color_map[cat] = '#D32F2F' # 深紅色 (失敗)
        elif "R0" in cat:
            color_map[cat] = '#4CAF50' # 綠色 (一次成功)
        elif "R1" in cat:
            color_map[cat] = '#8BC34A' # 淺綠
        elif "R2" in cat:
            color_map[cat] = '#FFC107' # 黃色
        elif "R3" in cat:
            color_map[cat] = '#FF9800' # 橘色
        else:
            color_map[cat] = 'gray'

    # --- 子圖 1: 柱狀圖 (平均時間) ---
    plt.subplot(2, 2, 1)
    means = df.groupby("category")["elapsed_us"].mean().reindex(categories)
    # 處理可能沒有數據的情況
    means = means.dropna()
    current_cats = means.index.tolist()
    
    if current_cats:
        bars = plt.bar(current_cats, means.values, color=[color_map.get(c, 'gray') for c in current_cats])
        plt.bar_label(bars, fmt='%.0f')
    
    plt.title("Average Time: Success vs Failure")
    plt.ylabel("Time (us)")
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    # --- 子圖 2: 盒鬚圖 (分佈) ---
    plt.subplot(2, 2, 2)
    dataset = []
    labels = []
    for cat in categories:
        subset = df[df['category'] == cat]['elapsed_us'].values
        if len(subset) > 0:
            dataset.append(subset)
            labels.append(cat)
            
    if dataset:
        bplot = plt.boxplot(dataset, labels=labels, patch_artist=True)
        # 設定盒鬚圖顏色
        for patch, label in zip(bplot['boxes'], labels):
            patch.set_facecolor(color_map.get(label, 'gray'))
            
    plt.title("Latency Distribution (Box Plot)")
    plt.xticks(rotation=45)
    plt.ylabel("Time (us)")
    plt.grid(True, linestyle='--', alpha=0.5)

    # --- 子圖 3: 散佈圖 (封包時間序列) ---
    plt.subplot(2, 1, 2)
    
    # 繪製 Success 點
    success_df = df[df['is_failure'] == False]
    if not success_df.empty:
        plt.scatter(success_df['index'], success_df['elapsed_us'], 
                    c='green', alpha=0.5, s=15, label='Success')
    
    # 繪製 Failure 點 (用紅色 X 標示)
    fail_df = df[df['is_failure'] == True]
    if not fail_df.empty:
        plt.scatter(fail_df['index'], fail_df['elapsed_us'], 
                    c='red', marker='x', s=50, linewidth=2, label='Failure')

    plt.title("Timeline: Latency per Packet")
    plt.xlabel("Packet Sequence (Log Line Index)")
    plt.ylabel("Time (us)")
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    
    # 儲存圖片到「當前執行目錄」，避免權限問題
    output_filename = "harq_analysis_result.png"
    plt.savefig(output_filename)
    print(f"圖表已成功儲存為: {output_filename}")
    # 若在支援 GUI 的環境下可取消註解下面這行
    # plt.show() 

# ==========================================
# 主程式入口
# ==========================================
if __name__ == "__main__":
    # 使用您的絕對路徑
    #log_file_path = "/home/hpe/openairinterface5g-develop-latest/cmake_targets/ran_build/build/harq_timing.txt"
    log_file_path = "/home/hpe/openairinterface5g/cmake_targets/ran_build/build/harq_timing.txt"

    # 檢查路徑是否存在
    if os.path.exists(log_file_path):
        analyze_harq_log_final(log_file_path)
    else:
        print(f"錯誤: 找不到指定路徑的檔案: {log_file_path}")
        print("請檢查路徑是否正確，或確認該檔案是否已生成。")
