import dash
from dash import dcc, html, Input, Output, Patch, State, ctx
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import re
import math
import os

# ==========================================
# 設定區
# ==========================================
FILE_MARGIN = '/home/hpe/openairinterface5g/cmake_targets/ran_build/build/learned_margin.txt'
CENTER_MARGIN = 500

FILE_PROFILE = '/home/hpe/openairinterface5g/cmake_targets/ran_build/build/slot_profile_us.txt'
CENTER_PROFILE = 0

HOST_IP = '0.0.0.0'
PORT = 8050
MAX_DISPLAY_POINTS = 1000

# ==========================================
# 視覺設定
# ==========================================
CUSTOM_COLORSCALE = [
    [0.0, '#c0392b'], [0.4, '#e74c3c'], [0.5, '#2c3e50'], [0.6, '#2980b9'], [1.0, '#3498db']
]
DELTA_RANGE = 20

# ==========================================
# 資料載入
# ==========================================
def load_data(path):
    if not os.path.exists(path):
        print(f"❌ 找不到檔案: {path}")
        return None, None, None

    timestamps, data_records, calc_focus_points = [], [], []
    pattern = re.compile(r'\[([\d\.]+)\]\s+(\d+)\.(\d+).*?\[([\d,\-\s]+)\]')

    try:
        print(f"📂 讀取: {path} ...")
        with open(path, 'r') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    ts = float(match.group(1))
                    frame, slot = int(match.group(2)), int(match.group(3))
                    array_str = match.group(4)
                    
                    if ',' in array_str:
                        curr_arr = np.fromstring(array_str, sep=',', dtype=int)
                    else:
                        curr_arr = np.fromstring(array_str, sep=' ', dtype=int)

                    timestamps.append(ts)
                    data_records.append(curr_arr)
                    
                    if len(curr_arr) > 0:
                        target_idx = (frame * 1024 + slot) % len(curr_arr)
                        calc_focus_points.append({'ts': ts, 'idx': target_idx, 'val': curr_arr[target_idx]})

        if not data_records: return None, None, None

        df_raw = pd.DataFrame(data_records, index=timestamps)
        df_raw.index.name = 'Timestamp'
        df_raw = df_raw.dropna(axis=1, how='all').fillna(method='ffill').fillna(0)
        df_delta = df_raw.diff().fillna(0)
        df_focus = pd.DataFrame(calc_focus_points)
        print(f"✅ 載入完成: {len(df_raw)} rows")
        return df_raw, df_delta, df_focus
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None, None

df_m_raw, df_m_delta, df_m_focus = load_data(FILE_MARGIN)
df_p_raw, df_p_delta, df_p_focus = load_data(FILE_PROFILE)

# ==========================================
# 核心功能：動態降採樣
# ==========================================
def get_downsampled_view(df_raw, df_delta, start_ts=None, end_ts=None, max_points=MAX_DISPLAY_POINTS):
    if start_ts is not None and end_ts is not None:
        ts_index = df_raw.index
        idx_start = ts_index.searchsorted(start_ts)
        idx_end = ts_index.searchsorted(end_ts)
        if idx_start >= idx_end: return pd.DataFrame(), pd.DataFrame()
        sub_raw = df_raw.iloc[max(0, idx_start-1) : idx_end+1]
        sub_delta = df_delta.iloc[max(0, idx_start-1) : idx_end+1]
    else:
        sub_raw = df_raw
        sub_delta = df_delta

    current_len = len(sub_raw)
    if current_len > max_points:
        step = int(np.ceil(current_len / max_points))
        return sub_raw.iloc[::step], sub_delta.iloc[::step]
    
    return sub_raw, sub_delta

# ==========================================
# 繪圖初始化 (視覺優化版)
# ==========================================
def create_initial_figure(df_raw, df_delta, df_focus, center_val):
    if df_raw is None:
        fig = go.Figure()
        fig.add_annotation(text="No Data", showarrow=False)
        return fig, 600

    d_raw, d_delta = get_downsampled_view(df_raw, df_delta)
    
    num_indices = df_raw.shape[1]
    COLS = 5
    ROWS = math.ceil(num_indices / COLS)
    ROW_HEIGHT = 250
    total_h = max(600, ROWS * ROW_HEIGHT)

    fig = make_subplots(
        rows=ROWS, cols=COLS, shared_xaxes=True, 
        vertical_spacing=0.08/ROWS if ROWS>0 else 0, horizontal_spacing=0.02,
        subplot_titles=[f"Index {i}" for i in range(num_indices)]
    )

    for i in range(num_indices):
        r, c = (i // COLS) + 1, (i % COLS) + 1
        
        # Main Trace
        fig.add_trace(go.Scattergl(
            x=d_raw.index, y=d_raw.iloc[:, i],
            mode='markers+lines', name=f'Idx {i}',
            line=dict(color='#bdc3c7', width=1),
            marker=dict(
                color=d_delta.iloc[:, i], colorscale=CUSTOM_COLORSCALE,
                cmin=-DELTA_RANGE, cmax=DELTA_RANGE, size=5, opacity=0.9,
                showscale=(i==0), 
                # 【優化】Colorbar 設定: 置中 (y=0.5)，縮短一點 (len=0.8) 避免太高
                colorbar=dict(len=0.8, y=0.5, x=1.01, title="Delta") if i==0 else None
            ),
            # 【優化】Hover 顯示高精度時間 (小數點後6位)，X軸則保持簡潔
            hovertemplate='<b>Time</b>: %{x:.6f}<br><b>Val</b>: %{y}<br><b>Delta</b>: %{marker.color}<extra></extra>'
        ), row=r, col=c)

        # Focus Trace
        f_subset = pd.DataFrame()
        if not df_focus.empty:
            f_subset = df_focus[df_focus['idx'] == i]
            if not f_subset.empty:
                 range_mask = (f_subset['ts'] >= d_raw.index.min()) & (f_subset['ts'] <= d_raw.index.max())
                 f_subset = f_subset[range_mask]

        fig.add_trace(go.Scattergl(
            x=f_subset['ts'] if not f_subset.empty else [],
            y=f_subset['val'] if not f_subset.empty else [],
            mode='markers', marker=dict(symbol='circle-open', size=12, color='#f39c12', line=dict(width=2.5)),
            name='Calc', showlegend=(i==0), hoverinfo='skip'
        ), row=r, col=c)

        # 軸範圍
        padding = 10
        if not d_raw.empty:
             diff = max(abs(d_raw.iloc[:,i].max() - center_val), abs(d_raw.iloc[:,i].min() - center_val))
             padding = max(5, diff * 1.2)
        
        y_name = f'yaxis{i+1}' if i > 0 else 'yaxis'
        fig.layout[y_name].update(range=[center_val-padding, center_val+padding], showgrid=True, zeroline=(center_val==0))

    # 【優化】Layout Margin 與 X軸格式
    fig.update_layout(
        height=total_h, template='plotly_white', 
        # t=80 (上邊距給標題), b=100 (加大下邊距給時間戳)
        margin=dict(t=80, b=100, l=40, r=40), 
        hovermode="x unified", showlegend=False
    )
    
    # 【優化】X軸設定
    fig.update_xaxes(
        matches='x', 
        showgrid=True,
        tickformat=".0f",     # 軸上只顯示整數部分 (避免 1.768B 或過多小數)
        exponentformat="none" # 禁止科學記號
    )
    return fig, total_h

# ==========================================
# App 結構
# ==========================================
app = dash.Dash(__name__, update_title=None)

fig_m, h_m = create_initial_figure(df_m_raw, df_m_delta, df_m_focus, CENTER_MARGIN)
fig_p, h_p = create_initial_figure(df_p_raw, df_p_delta, df_p_focus, CENTER_PROFILE)

app.layout = html.Div([
    dcc.Store(id='shared-zoom-store'),

    html.Div([
        html.H3("OAI System Monitor", style={'display':'inline-block', 'margin':0, 'color':'#2c3e50'}),
        html.Span(" (UI Optimized | Synced)", style={'marginLeft':10, 'color':'#27ae60', 'fontWeight':'bold'})
    ], style={'padding':15, 'borderBottom':'1px solid #ddd'}),
    
    dcc.Tabs([
        dcc.Tab(label='Learned Margin (Center 500)', children=[
            html.Div([
                dcc.Graph(id='g-margin', figure=fig_m, config={'scrollZoom':True}, style={'height': f'{h_m}px'})
            ], style={'paddingTop': '20px'})
        ]),
        dcc.Tab(label='Slot Profile (Center 0)', children=[
            html.Div([
                dcc.Graph(id='g-profile', figure=fig_p, config={'scrollZoom':True}, style={'height': f'{h_p}px'})
            ], style={'paddingTop': '20px'})
        ])
    ])
])

# ==========================================
# 邏輯 1: 匯總縮放事件 (Sync Logic)
# ==========================================
@app.callback(
    Output('shared-zoom-store', 'data'),
    [Input('g-margin', 'relayoutData'),
     Input('g-profile', 'relayoutData')],
    prevent_initial_call=True
)
def sync_zoom(relayout_m, relayout_p):
    trigger_id = ctx.triggered_id
    if not trigger_id: return dash.no_update
    
    data = relayout_m if trigger_id == 'g-margin' else relayout_p
    if not data: return dash.no_update

    if 'xaxis.range[0]' in data:
        return {'range': [data['xaxis.range[0]'], data['xaxis.range[1]']]}
    elif 'xaxis.range' in data:
        return {'range': [data['xaxis.range'][0], data['xaxis.range'][1]]}
    elif 'xaxis.autorange' in data:
        return {'range': None}
    
    return dash.no_update

# ==========================================
# 邏輯 2: 統一更新兩個圖表 (Patch Update)
# ==========================================
def create_patch(df_raw, df_delta, df_focus, center_val, x_range):
    patch = Patch()
    if x_range is None:
        d_r, d_d = get_downsampled_view(df_raw, df_delta)
    else:
        d_r, d_d = get_downsampled_view(df_raw, df_delta, x_range[0], x_range[1])
    
    if d_r.empty: return patch

    num_indices = df_raw.shape[1]
    for i in range(num_indices):
        main_trace_idx = i * 2
        focus_trace_idx = i * 2 + 1
        
        patch['data'][main_trace_idx]['x'] = d_r.index
        patch['data'][main_trace_idx]['y'] = d_r.iloc[:, i]
        patch['data'][main_trace_idx]['marker']['color'] = d_d.iloc[:, i]
        
        series = d_r.iloc[:, i]
        diff = max(abs(series.max() - center_val), abs(series.min() - center_val))
        padding = max(5, diff * 1.2)
        y_name = f'yaxis{i+1}' if i > 0 else 'yaxis'
        patch['layout'][y_name]['range'] = [center_val - padding, center_val + padding]
        
        if not df_focus.empty:
            f_sub = df_focus[df_focus['idx'] == i]
            if not f_sub.empty:
                if x_range:
                    mask = (f_sub['ts'] >= x_range[0]) & (f_sub['ts'] <= x_range[1])
                    f_sub = f_sub[mask]
                patch['data'][focus_trace_idx]['x'] = f_sub['ts']
                patch['data'][focus_trace_idx]['y'] = f_sub['val']
            else:
                patch['data'][focus_trace_idx]['x'] = []
                patch['data'][focus_trace_idx]['y'] = []

    return patch

@app.callback(
    [Output('g-margin', 'figure'),
     Output('g-profile', 'figure')],
    Input('shared-zoom-store', 'data'),
    prevent_initial_call=True
)
def update_both_graphs(zoom_data):
    if zoom_data is None: return dash.no_update, dash.no_update
    
    x_range = zoom_data.get('range')
    patch_m = create_patch(df_m_raw, df_m_delta, df_m_focus, CENTER_MARGIN, x_range)
    patch_p = create_patch(df_p_raw, df_p_delta, df_p_focus, CENTER_PROFILE, x_range)
    
    return patch_m, patch_p

if __name__ == '__main__':
    print(f"🚀 Server running on http://{HOST_IP}:{PORT}")
    app.run(host=HOST_IP, port=PORT, debug=False)
