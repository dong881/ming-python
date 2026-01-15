import dash
from dash import dcc, html, Input, Output, State, no_update
import plotly.graph_objects as go
import pandas as pd
import re
import os
import numpy as np

# ================= 設定區 =================
INPUT_FILE_PATH = '/home/oai72_su/oai_mp_f_ming/openairinterface5g/cmake_targets/ran_build/build/margin.txt'
SERVER_PORT = 8050
SERVER_HOST = '0.0.0.0'
# 設定閾值：當視野內的點少於此數量時，顯示精確座標；否則顯示均勻刻度
EXACT_TICK_THRESHOLD = 40 
# =========================================

def parse_log_file(filepath):
    if not os.path.exists(filepath):
        print(f"❌ 錯誤: 找不到檔案 {filepath}")
        return pd.DataFrame()

    print(f"📂 正在讀取檔案: {filepath} ...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        pattern = re.compile(r"\[([\d\.]+)\]\s+(\d+)\.(\d+)\s+m:(-?\d+),\s+(.*)")
        matches = pattern.findall(content)
        
        if not matches:
            print("⚠️ 警告: 檔案中沒有匹配到任何符合格式的數據！")
            return pd.DataFrame()
            
        df = pd.DataFrame(matches, columns=['timestamp', 'sfn', 'slot', 'm', 'message'])
        df['timestamp'] = df['timestamp'].astype(float)
        df['sfn'] = df['sfn'].astype(int)
        df['slot'] = df['slot'].astype(int)
        df['m'] = df['m'].astype(int)
        
        # 1. 排序
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # 2. SFN Unwrapping (線性化)
        sfn_diff = df['sfn'].diff()
        wrap_indices = sfn_diff < -500 
        
        df['hyper_adder'] = 0
        df.loc[wrap_indices, 'hyper_adder'] = 1024
        df['hyper_adder'] = df['hyper_adder'].cumsum()
        
        # 3. 計算 Linear X (Slot Index)
        df['linear_x'] = (df['sfn'] + df['hyper_adder']) * 20 + df['slot']
        
        print(f"✅ 成功載入 {len(df)} 筆數據。")
        return df

    except Exception as e:
        print(f"❌ 讀取檔案時發生錯誤: {e}")
        return pd.DataFrame()

# --- 資料載入 ---
df = parse_log_file(INPUT_FILE_PATH)

app = dash.Dash(__name__)

def convert_linear_to_label(val_array):
    """將 Linear X 數值陣列轉換為 SFN.SLOT 字串列表"""
    labels = []
    for val in val_array:
        sfn = (int(val) // 20) % 1024
        slot = int(val) % 20
        labels.append(f"{sfn}.{slot}")
    return labels

def create_base_figure(dframe):
    fig = go.Figure()
    if dframe.empty:
        return fig.update_layout(title="No Data Found")

    # 1. 滑動條層
    target_points = 1000
    step = max(1, len(dframe) // target_points)
    df_lite = dframe.iloc[::step].copy()
    y_max, y_min = df_lite['m'].max(), df_lite['m'].min()
    if y_max != y_min:
        df_lite['m_norm'] = 0.1 + 0.8 * (df_lite['m'] - y_min) / (y_max - y_min)
    else:
        df_lite['m_norm'] = 0.5

    fig.add_trace(go.Scatter(
        x=df_lite['linear_x'], y=df_lite['m_norm'], mode='lines',
        line=dict(width=1, color='#666'), fill='tozeroy', fillcolor='rgba(100,100,100,0.2)',
        yaxis='y2', showlegend=False, hoverinfo='skip'
    ))

    # 2. 全域連線層
    fig.add_trace(go.Scattergl(
        x=dframe['linear_x'], y=dframe['m'], mode='lines', name='Sequence',
        line=dict(width=1, color='rgba(150, 150, 150, 0.5)'), hoverinfo='skip', showlegend=False
    ))

    # 3. 數據點層
    messages = dframe['message'].unique()
    for msg in messages:
        subset = dframe[dframe['message'] == msg]
        fig.add_trace(go.Scattergl(
            x=subset['linear_x'], y=subset['m'], mode='markers', name=msg,
            marker=dict(size=7, line=dict(width=1, color='#888')),
            customdata=np.stack((subset['sfn'], subset['slot'], subset['message']), axis=-1),
            hovertemplate="<b>%{customdata[2]}</b><br>SFN.Slot: %{customdata[0]}.%{customdata[1]}<br>m: %{y}<extra></extra>"
        ))

    # 4. 異常點層
    neg_df = dframe[dframe['m'] < 0]
    if not neg_df.empty:
        fig.add_trace(go.Scattergl(
            x=neg_df['linear_x'], y=neg_df['m'], mode='markers', name='Warning (m<0)',
            marker=dict(size=11, color='rgba(0,0,0,0)', line=dict(color='red', width=2), symbol='circle'),
            hoverinfo='skip'
        ))

    # 初始刻度 (全域使用均勻刻度)
    init_min, init_max = dframe['linear_x'].min(), dframe['linear_x'].max()
    init_ticks = np.linspace(init_min, init_max, 15, dtype=int)
    init_labels = convert_linear_to_label(init_ticks)

    fig.update_layout(
        title=f'Margin Analysis (Adaptive Precise Ticking)',
        xaxis_title='Time (SFN.SLOT)',
        yaxis_title='Margin Value (m)',
        template='plotly_white',
        hovermode='closest',
        height=850,
        
        xaxis=dict(
            tickmode='array',
            tickvals=init_ticks,
            ticktext=init_labels,
            rangeslider=dict(visible=True, thickness=0.15, bgcolor='#eeeeee', yaxis=dict(rangemode='fixed'))
        ),
        
        yaxis=dict(autorange=True, fixedrange=False, domain=[0.2, 1]),
        yaxis2=dict(domain=[0, 0.15], range=[0, 1], visible=False, fixedrange=True),
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01),
        margin=dict(l=60, r=50, t=50, b=50)
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    return fig

initial_fig = create_base_figure(df)

app.layout = html.Div([
    html.H2("OAI Margin Analysis Dashboard", style={'textAlign': 'center', 'fontFamily': 'Arial'}),
    dcc.Loading(
        dcc.Graph(
            id='margin-graph',
            figure=initial_fig,
            style={'height': '90vh'},
            config={'scrollZoom': True, 'displayModeBar': True} 
        )
    )
])

# --- 核心邏輯：自適應 X 軸標籤 ---
@app.callback(
    Output('margin-graph', 'figure'),
    Input('margin-graph', 'relayoutData'),
    State('margin-graph', 'figure')
)
def update_view(relayout_data, current_fig):
    if df.empty or relayout_data is None:
        return no_update

    layout = current_fig['layout']
    
    # 1. 處理重置
    if 'xaxis.autorange' in relayout_data:
        layout['yaxis']['range'] = [df['m'].min() - 5, df['m'].max() + 5]
        all_min, all_max = df['linear_x'].min(), df['linear_x'].max()
        ticks = np.linspace(all_min, all_max, 15, dtype=int)
        layout['xaxis']['tickvals'] = ticks
        layout['xaxis']['ticktext'] = convert_linear_to_label(ticks)
        return current_fig

    # 2. 取得 X 軸範圍
    x_start, x_end = None, None
    if 'xaxis.range[0]' in relayout_data:
        x_start, x_end = relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']
    elif 'xaxis.range' in relayout_data:
        x_start, x_end = relayout_data['xaxis.range'][0], relayout_data['xaxis.range'][1]
    
    if x_start is not None and x_end is not None:
        has_changes = False
        
        # 篩選當前視野內的數據
        mask = (df['linear_x'] >= x_start) & (df['linear_x'] <= x_end)
        filtered_data = df[mask]
        
        # --- A. 動態更新 Y 軸 ---
        if not filtered_data.empty:
            y_min, y_max = filtered_data['m'].min(), filtered_data['m'].max()
            padding = (y_max - y_min) * 0.1 if y_max != y_min else 5
            padding = 5 if padding == 0 else padding
            layout['yaxis']['range'] = [y_min - padding, y_max + padding]
            layout['yaxis']['autorange'] = False
            has_changes = True

        # --- B. 自適應 X 軸標籤 (Adaptive Ticking) ---
        visible_count = len(filtered_data)
        
        # 如果數據點很少 (小於閾值)，且不為空 -> 顯示精確座標
        if 0 < visible_count <= EXACT_TICK_THRESHOLD:
            # 取得所有唯一 X 座標 (去除同一 Slot 重複點)
            precise_ticks = np.sort(filtered_data['linear_x'].unique())
            layout['xaxis']['tickvals'] = precise_ticks
            layout['xaxis']['ticktext'] = convert_linear_to_label(precise_ticks)
            has_changes = True
            
        # 如果數據點太多 -> 使用均勻刻度 (避免卡頓)
        elif visible_count > EXACT_TICK_THRESHOLD:
            # 產生 15 個均勻刻度
            grid_ticks = np.linspace(x_start, x_end, 15, dtype=int)
            layout['xaxis']['tickvals'] = grid_ticks
            layout['xaxis']['ticktext'] = convert_linear_to_label(grid_ticks)
            has_changes = True
            
        # 如果完全沒數據 (例如拖到空白處) -> 保持均勻刻度
        elif visible_count == 0:
            grid_ticks = np.linspace(x_start, x_end, 15, dtype=int)
            layout['xaxis']['tickvals'] = grid_ticks
            layout['xaxis']['ticktext'] = convert_linear_to_label(grid_ticks)
            has_changes = True

        if has_changes:
            return current_fig

    return no_update

if __name__ == '__main__':
    print("------------------------------------------------------------------")
    print(f"🚀 伺服器已啟動: http://{SERVER_HOST}:{SERVER_PORT}")
    print("------------------------------------------------------------------")
    app.run(debug=False, host=SERVER_HOST, port=SERVER_PORT)
