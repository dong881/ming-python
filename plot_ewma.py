import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import re
import os
import numpy as np
import socket

# ================= 設定區 =================
# 請確認此路徑正確，或修改為您的測試檔案路徑
INPUT_FILE_PATH = '/home/hpe/gNB-logs/nfapi-VNF-pegatron-localcn-develop-latest-ming-develop.log'
DEFAULT_PORT = 8050
SERVER_HOST = '0.0.0.0'
# =========================================

def parse_log_file(filepath):
    """
    解析 Log 格式: 
    1506853.277786 [I] 3330262592: vnf_p7_convergence_optimization: (-1005, -1200, 195)
    對應: timestamp, val_1, val_2, val_3
    """
    if not os.path.exists(filepath):
        print(f"❌ 錯誤: 找不到檔案 {filepath}")
        return pd.DataFrame()

    print(f"📂 正在讀取檔案: {filepath} ...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex 更新: 
        # Group 1: Timestamp (浮點數)
        # Group 2: Value 1 (整數)
        # Group 3: Value 2 (整數)
        # Group 4: Value 3 (整數)
        # 匹配邏輯: 抓取 timestamp，忽略中間雜訊，直到找到 vnf_p7...: 後面的括號內容
        pattern = re.compile(r"([\d\.]+)\s+\[I\].*?vnf_p7_convergence_optimization:\s*\((-?\d+),\s*(-?\d+),\s*(-?\d+)\)")
        matches = pattern.findall(content)

        if not matches:
            print("⚠️ 警告: 檔案中沒有匹配到任何符合格式的數據！")
            # 這是為了調試用，印出前幾行看看為什麼沒匹配到
            print(f"檔案前 200 字元預覽: {content[:200]}")
            return pd.DataFrame()

        # 建立 DataFrame
        columns = ['timestamp', 'val_1', 'val_2', 'val_3']
        df = pd.DataFrame(matches, columns=columns)

        # 轉換型別
        for col in columns:
            df[col] = df[col].astype(float)
        
        # 排序
        df = df.sort_values('timestamp').reset_index(drop=True)

        print(f"✅ 成功載入 {len(df)} 筆數據。")
        return df

    except Exception as e:
        print(f"❌ 讀取檔案時發生錯誤: {e}")
        return pd.DataFrame()

# --- 資料載入 ---
df = parse_log_file(INPUT_FILE_PATH)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

# 初始圖表
initial_fig = go.Figure()
initial_fig.update_layout(
    title={'text': 'Loading Data...', 'x': 0.5},
    template='plotly_white',
    xaxis={'visible': False}, yaxis={'visible': False}
)

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("📉 Convergence Optimization Analyzer", className="text-primary fw-bold my-3"), width=12)
    ], className="border-bottom mb-3"),

    dbc.Row([
        # 左側圖表區
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(
                        dcc.Graph(
                            id='main-graph',
                            figure=initial_fig,
                            style={'height': '85vh'},
                            config={'scrollZoom': True, 'displayModeBar': True}
                        ),
                        type="cube", color="#2c3e50"
                    )
                ], style={'padding': '0'})
            ], className="shadow-sm border-0")
        ], width=11),

        # 右側控制面板
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🛠️ Filter", className="bg-primary text-white fw-bold py-2 text-center", style={'fontSize': '1rem'}),
                dbc.CardBody([
                    # 顯示項目開關
                    html.Label("Metrics:", className="fw-bold small"),
                    dbc.Checklist(
                        id='metric-filter',
                        options=[
                            {'label': ' Value 1', 'value': 'val_1'},
                            {'label': ' Value 2', 'value': 'val_2'},
                            {'label': ' Value 3', 'value': 'val_3'},
                        ],
                        value=['val_1', 'val_2', 'val_3'], # 預設全選
                        switch=False,
                        inputStyle={"marginRight": "5px"},
                        style={'fontSize': '0.9rem'}
                    ),
                    
                    html.Hr(),
                    html.Div("Log Data Visualization", className="text-muted small text-center")

                ], style={'padding': '10px'})
            ], className="shadow-sm border-0 h-100")
        ], width=1, style={'minWidth': '120px', 'maxWidth': '140px'})
    ], className="g-1")
], fluid=True, style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh', 'padding': '5px'})

# --- Callback: 核心繪圖 ---
@app.callback(
    Output('main-graph', 'figure'),
    [Input('metric-filter', 'value'),
     Input('main-graph', 'relayoutData')],
    [State('main-graph', 'figure')]
)
def update_graph(selected_metrics, relayout_data, current_fig_dict):
    if df.empty:
        # 如果沒有數據，回傳空圖表但保留標題
        empty_fig = go.Figure()
        empty_fig.update_layout(title={'text': 'No Data Found / Parse Error', 'x': 0.5})
        return empty_fig

    if selected_metrics is None:
        selected_metrics = []
    
    fig = go.Figure()

    # 定義顏色與樣式
    styles = {
        'val_1': {'color': '#e74c3c', 'name': 'Val 1', 'width': 1.5}, # 紅色
        'val_2': {'color': '#3498db', 'name': 'Val 2', 'width': 1.5}, # 藍色
        'val_3': {'color': '#2ecc71', 'name': 'Val 3', 'width': 1.5}, # 綠色
    }

    # 繪製選定的線條
    for metric in selected_metrics:
        if metric in df.columns:
            style = styles.get(metric, {'color': '#000000', 'name': metric, 'width': 1})
            
            fig.add_trace(go.Scattergl(
                x=df['timestamp'], 
                y=df[metric],
                mode='lines+markers',
                name=style['name'],
                line=dict(width=style['width'], color=style['color']),
                marker=dict(size=4),
                hovertemplate=f"<b>{style['name']}: %{{y}}</b><br>Time: %{{x}}<extra></extra>"
            ))

    # --- 保持視圖狀態 (Zoom Persistence) ---
    dragmode = 'zoom'
    x_range = None
    
    # 繼承 Dragmode
    if current_fig_dict and 'layout' in current_fig_dict:
        dragmode = current_fig_dict['layout'].get('dragmode', 'zoom')
    if relayout_data and 'dragmode' in relayout_data:
        dragmode = relayout_data['dragmode']

    # 處理 Zoom Range
    is_zoomed = False
    if relayout_data:
        if 'xaxis.range[0]' in relayout_data:
            x_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
            is_zoomed = True
        elif 'xaxis.range' in relayout_data:
            x_range = relayout_data['xaxis.range']
            is_zoomed = True

    if not is_zoomed and current_fig_dict and 'layout' in current_fig_dict and relayout_data is not None:
         try:
            old_x = current_fig_dict['layout'].get('xaxis', {}).get('range', None)
            if old_x: x_range = old_x
         except:
            pass

    # Layout Styling
    fig.update_layout(
        title={'text': 'Optimization Values Over Time', 'font': {'size': 20, 'color': '#2c3e50'}},
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis_title='Timestamp (s)',
        yaxis_title='Value',
        template='plotly_white',
        hovermode='x unified',
        height=750,
        dragmode=dragmode,
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.05),
            gridcolor='#ecf0f1', 
            showspikes=True, spikemode='across', spikesnap='cursor', showline=True, linewidth=1, linecolor='black'
        ),
        yaxis=dict(gridcolor='#ecf0f1', zeroline=True, zerolinecolor='#bdc3c7'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=80, b=40)
    )

    # 應用 Range 並自適應 Y 軸
    if x_range:
        fig.update_layout(xaxis=dict(range=x_range, autorange=False))
        # 計算可視範圍內的 Y 軸範圍
        mask = (df['timestamp'] >= x_range[0]) & (df['timestamp'] <= x_range[1])
        view_df = df[mask]
        if not view_df.empty and selected_metrics:
            current_vals = view_df[selected_metrics].values.flatten()
            current_vals = current_vals[~np.isnan(current_vals)]
            if len(current_vals) > 0:
                y_min, y_max = np.min(current_vals), np.max(current_vals)
                padding = (y_max - y_min) * 0.1 if y_max != y_min else 5
                fig.update_layout(yaxis=dict(range=[y_min - padding, y_max + padding], autorange=False))

    return fig

# --- Port 衝突檢測與啟動 ---
def find_free_port(start_port):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            print(f"⚠️ Port {port} 被佔用，嘗試 {port + 1}...")
            port += 1

if __name__ == '__main__':
    target_port = find_free_port(DEFAULT_PORT)
    
    print("------------------------------------------------------------------")
    print(f"🚀 伺服器已啟動: http://{SERVER_HOST}:{target_port}")
    print(f"📊 監控日誌: {INPUT_FILE_PATH}")
    print("------------------------------------------------------------------")
    
    app.run(debug=False, host=SERVER_HOST, port=target_port)
