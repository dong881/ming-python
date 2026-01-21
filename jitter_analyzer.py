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
INPUT_FILE_PATH = '/home/hpe/gNB-logs/nfapi-VNF-pegatron-localcn-develop-latest-ming-develop.log'
DEFAULT_PORT = 8050
SERVER_HOST = '0.0.0.0'
# =========================================

def parse_log_file(filepath):
    """
    針對新的 JITTER_DEBUG 格式進行解析
    格式範例: 
    1328073.745199 [I] ... [JITTER_DEBUG] slot:0 jitter:97 j_avg:87 diff:48 late:-267 early:-315 margin:343
    """
    if not os.path.exists(filepath):
        print(f"❌ 錯誤: 找不到檔案 {filepath}")
        return pd.DataFrame()

    print(f"📂 正在讀取檔案: {filepath} ...")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex 對應提供的 Log 格式
        # Group 1: Timestamp, 2: Slot, 3: Jitter, 4: J_avg, 5: Diff, 6: Late, 7: Early, 8: Margin
        pattern = re.compile(r"([\d\.]+)\s+\[I\].*?\[JITTER_DEBUG\]\s+slot:(\d+)\s+jitter:(-?\d+)\s+j_avg:(-?\d+)\s+diff:(-?\d+)\s+late:(-?\d+)\s+early:(-?\d+)\s+margin:(-?\d+)")
        matches = pattern.findall(content)

        if not matches:
            print("⚠️ 警告: 檔案中沒有匹配到任何 [JITTER_DEBUG] 格式的數據！")
            return pd.DataFrame()

        # 建立 DataFrame
        columns = ['timestamp', 'slot', 'jitter', 'j_avg', 'diff', 'late', 'early', 'margin']
        df = pd.DataFrame(matches, columns=columns)

        # 轉換型別
        for col in columns:
            df[col] = df[col].astype(float) # 統一轉 float 方便繪圖
        
        df['slot'] = df['slot'].astype(int)

        # 排序
        df = df.sort_values('timestamp').reset_index(drop=True)

        print(f"✅ 成功載入 {len(df)} 筆 Jitter 數據。")
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

# --- Layout (維持你原本的參考風格) ---
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("📉 Jitter & Sync Analyzer", className="text-primary fw-bold my-3"), width=12)
    ], className="border-bottom mb-3"),

    dbc.Row([
        # 左側圖表區
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(
                        dcc.Graph(
                            id='jitter-graph',
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
                    # 全選/清除按鈕
                    dbc.ButtonGroup([
                        dbc.Button("All", id="btn-all", color="success", outline=True, size="sm", style={'padding': '2px'}),
                        dbc.Button("Clr", id="btn-none", color="danger", outline=True, size="sm", style={'padding': '2px'}),
                    ], className="d-flex w-100 mb-2"),

                    # Slot 篩選
                    html.Div([
                        dbc.Checklist(
                            id='slot-filter',
                            options=[{'label': f' S{i}', 'value': i} for i in range(20)], 
                            value=list(range(20)),
                            switch=True,
                            className="slot-checklist",
                            style={'fontSize': '0.8rem'}
                        )
                    ], style={'maxHeight': '40vh', 'overflowY': 'auto', 'padding': '0', 'borderBottom': '1px solid #eee'}),
                    
                    html.Hr(className="my-2"),
                    
                    # 顯示項目開關 (新增功能)
                    html.Label("Metrics:", className="fw-bold small"),
                    dbc.Checklist(
                        id='metric-filter',
                        options=[
                            {'label': ' Jitter', 'value': 'jitter'},
                            {'label': ' J_Avg', 'value': 'j_avg'},
                            {'label': ' Diff', 'value': 'diff'},
                            {'label': ' Margin', 'value': 'margin'},
                        ],
                        value=['jitter', 'j_avg', 'diff'], # 預設顯示這三個
                        switch=False,
                        inputStyle={"marginRight": "5px"}
                    )

                ], style={'padding': '5px'})
            ], className="shadow-sm border-0 h-100")
        ], width=1, style={'minWidth': '120px', 'maxWidth': '140px'})
    ], className="g-1")
], fluid=True, style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh', 'padding': '5px'})

# --- Callback 1: Slot 全選/清空 ---
@app.callback(
    Output('slot-filter', 'value'),
    [Input('btn-all', 'n_clicks'), Input('btn-none', 'n_clicks')],
    [State('slot-filter', 'options')]
)
def update_slot_checklist(btn_all, btn_none, options):
    ctx = dash.callback_context
    if not ctx.triggered:
        return list(range(20))
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'btn-all':
        return list(range(20))
    elif button_id == 'btn-none':
        return []
    return list(range(20))

# --- Callback 2: 核心繪圖 ---
@app.callback(
    Output('jitter-graph', 'figure'),
    [Input('slot-filter', 'value'),
     Input('metric-filter', 'value'),
     Input('jitter-graph', 'relayoutData')],
    [State('jitter-graph', 'figure')]
)
def update_graph(selected_slots, selected_metrics, relayout_data, current_fig_dict):
    if df.empty:
        return no_update

    if selected_slots is None:
        selected_slots = list(range(20))
    
    if selected_metrics is None:
        selected_metrics = []

    # 1. 資料篩選
    filtered_df = df[df['slot'].isin(selected_slots)]
    
    fig = go.Figure()

    if not filtered_df.empty:
        # 定義顏色與樣式
        styles = {
            'jitter': {'color': '#e74c3c', 'name': 'Jitter', 'width': 1.5}, # 紅色
            'j_avg':  {'color': '#3498db', 'name': 'J_Avg',  'width': 2},   # 藍色
            'diff':   {'color': '#f1c40f', 'name': 'Diff',   'width': 1.5}, # 黃色
            'margin': {'color': '#2ecc71', 'name': 'Margin', 'width': 1},   # 綠色
        }

        # 繪製選定的線條
        for metric in selected_metrics:
            if metric in filtered_df.columns:
                fig.add_trace(go.Scattergl(
                    x=filtered_df['timestamp'], 
                    y=filtered_df[metric],
                    mode='lines+markers',
                    name=styles[metric]['name'],
                    line=dict(width=styles[metric]['width'], color=styles[metric]['color']),
                    marker=dict(size=4),
                    hovertemplate=f"<b>{styles[metric]['name']}: %{{y}}</b><br>Slot: %{{customdata[0]}}<extra></extra>",
                    customdata=np.stack((filtered_df['slot'],), axis=-1)
                ))

    else:
        fig.update_layout(title={'text': 'No Data Selected', 'x': 0.5})

    # --- 保持視圖狀態 (Zoom Persistence) ---
    dragmode = 'zoom'
    x_range = None
    y_range = None
    
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

    # 若非使用者縮放，嘗試繼承舊視圖 (切換 checkbox 時不跳回全覽)
    if not is_zoomed and current_fig_dict and 'layout' in current_fig_dict and relayout_data is not None:
         try:
            old_x = current_fig_dict['layout'].get('xaxis', {}).get('range', None)
            if old_x: x_range = old_x
         except:
            pass

    # Layout Styling
    fig.update_layout(
        title={'text': 'Jitter / Avg / Diff Analysis', 'font': {'size': 20, 'color': '#2c3e50'}},
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis_title='Timestamp (s)',
        yaxis_title='Value',
        template='plotly_white',
        hovermode='x unified', # 改用統一 hover 方便比較同一時間點的數值
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

    # 應用 Range
    if x_range:
        fig.update_layout(xaxis=dict(range=x_range, autorange=False))
        # Y 軸自適應 (根據目前視圖內的數據計算)
        if not filtered_df.empty:
            mask = (filtered_df['timestamp'] >= x_range[0]) & (filtered_df['timestamp'] <= x_range[1])
            view_df = filtered_df[mask]
            if not view_df.empty and selected_metrics:
                # 計算所有選定 metric 在目前視圖的最大最小值
                current_vals = view_df[selected_metrics].values.flatten()
                y_min, y_max = np.nanmin(current_vals), np.nanmax(current_vals)
                padding = (y_max - y_min) * 0.1 if y_max != y_min else 5
                fig.update_layout(yaxis=dict(range=[y_min - padding, y_max + padding], autorange=False))

    return fig

# --- Port 衝突檢測與啟動 ---
def find_free_port(start_port):
    """從 start_port 開始尋找可用的 port"""
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
