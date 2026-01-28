import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import re
import os
import numpy as np

# ================= 設定區 =================
INPUT_FILE_PATH = '/home/oai72_su/oai_mp_f_ming/openairinterface5g/cmake_targets/ran_build/build/logs/margin.txt.000'
SERVER_PORT = 8050
SERVER_HOST = '0.0.0.0'
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
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        sfn_diff = df['sfn'].diff()
        wrap_indices = sfn_diff < -500 
        df['hyper_adder'] = 0
        df.loc[wrap_indices, 'hyper_adder'] = 1024
        df['hyper_adder'] = df['hyper_adder'].cumsum()
        
        df['linear_x'] = (df['sfn'] + df['hyper_adder']) * 20 + df['slot']
        
        print(f"✅ 成功載入 {len(df)} 筆數據。")
        return df

    except Exception as e:
        print(f"❌ 讀取檔案時發生錯誤: {e}")
        return pd.DataFrame()

# --- 資料載入 ---
df = parse_log_file(INPUT_FILE_PATH)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

def convert_linear_to_label(val_array):
    labels = []
    for val in val_array:
        sfn = (int(val) // 20) % 1024
        slot = int(val) % 20
        labels.append(f"{sfn}.{slot}")
    return labels

# 初始圖表
initial_fig = go.Figure()
initial_fig.update_layout(
    title={'text': 'Loading Data...', 'x': 0.5},
    template='plotly_white',
    xaxis={'visible': False}, yaxis={'visible': False}
)

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("📊 OAI Margin Analyzer", className="text-primary fw-bold my-3"), width=12)
    ], className="border-bottom mb-3"),

    dbc.Row([
        # 左側圖表區 (佔 11/12，極致寬度)
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Loading(
                        dcc.Graph(
                            id='margin-graph',
                            figure=initial_fig,
                            style={'height': '85vh'},
                            config={'scrollZoom': True, 'displayModeBar': True} 
                        ),
                        type="cube", color="#2c3e50"
                    )
                ], style={'padding': '0'}) 
            ], className="shadow-sm border-0")
        ], width=11), # <--- 改成 11

        # 右側控制面板 (佔 1/12，極致窄版)
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🛠️", className="bg-primary text-white fw-bold py-2 text-center", style={'fontSize': '1rem'}),
                dbc.CardBody([
                    dbc.ButtonGroup([
                        dbc.Button("All", id="btn-all", color="success", outline=True, size="sm", style={'padding': '2px'}),
                        dbc.Button("Clr", id="btn-none", color="danger", outline=True, size="sm", style={'padding': '2px'}),
                    ], className="d-flex w-100 mb-2"),
                    
                    html.Div([
                        dbc.Checklist(
                            id='slot-filter',
                            options=[{'label': f' S{i}', 'value': i} for i in range(20)], # 縮寫 Label: Slot 0 -> S0
                            value=list(range(20)), 
                            switch=True, 
                            className="slot-checklist",
                            style={'fontSize': '0.8rem'} 
                        )
                    ], style={'maxHeight': '75vh', 'overflowY': 'auto', 'padding': '0'})
                ], style={'padding': '5px'}) 
            ], className="shadow-sm border-0 h-100")
        ], width=1, style={'minWidth': '120px', 'maxWidth': '140px'}) # <--- 強制限制寬度
    ], className="g-1") # 極小間距
], fluid=True, style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh', 'padding': '5px'})

# --- Callback 1: 全選/清空 ---
@app.callback(
    Output('slot-filter', 'value'),
    [Input('btn-all', 'n_clicks'), Input('btn-none', 'n_clicks')],
    [State('slot-filter', 'options')]
)
def update_checklist(btn_all, btn_none, options):
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
    Output('margin-graph', 'figure'),
    [Input('slot-filter', 'value'),
     Input('margin-graph', 'relayoutData')],
    [State('margin-graph', 'figure')]
)
def update_graph(selected_slots, relayout_data, current_fig_dict):
    if df.empty:
        return no_update

    if selected_slots is None: 
        selected_slots = list(range(20))
    
    filtered_df = df[df['slot'].isin(selected_slots)]
    
    fig = go.Figure()

    if not filtered_df.empty:
        # 1. Navigation Layer
        target_points = 1000
        step = max(1, len(filtered_df) // target_points)
        df_lite = filtered_df.iloc[::step].copy()
        y_max, y_min = df_lite['m'].max(), df_lite['m'].min()
        if y_max != y_min:
            df_lite['m_norm'] = 0.1 + 0.8 * (df_lite['m'] - y_min) / (y_max - y_min)
        else:
            df_lite['m_norm'] = 0.5

        fig.add_trace(go.Scatter(
            x=df_lite['linear_x'], y=df_lite['m_norm'], mode='lines',
            line=dict(width=1, color='#95a5a6'), fill='tozeroy', fillcolor='rgba(149, 165, 166, 0.2)',
            yaxis='y2', showlegend=False, hoverinfo='skip'
        ))

        # 2. Sequence
        fig.add_trace(go.Scattergl(
            x=filtered_df['linear_x'], y=filtered_df['m'], mode='lines', name='Sequence',
            line=dict(width=1, color='rgba(189, 195, 199, 0.5)'), hoverinfo='skip', showlegend=False
        ))

        # 3. Markers (width=0 解決白邊)
        messages = filtered_df['message'].unique()
        colors = ['#3498db', '#e67e22', '#2ecc71', '#9b59b6', '#f1c40f', '#1abc9c']
        
        for i, msg in enumerate(messages):
            subset = filtered_df[filtered_df['message'] == msg]
            color = colors[i % len(colors)]
            fig.add_trace(go.Scattergl(
                x=subset['linear_x'], y=subset['m'], mode='markers', name=msg,
                marker=dict(size=8, color=color, line=dict(width=0)), 
                customdata=np.stack((subset['sfn'], subset['slot'], subset['message']), axis=-1),
                hovertemplate="<b>%{customdata[2]}</b><br>SFN.Slot: %{customdata[0]}.%{customdata[1]}<br>m: %{y}<extra></extra>"
            ))

        # 4. Warnings
        neg_df = filtered_df[filtered_df['m'] < 0]
        if not neg_df.empty:
            fig.add_trace(go.Scattergl(
                x=neg_df['linear_x'], y=neg_df['m'], mode='markers', name='Warning (m<0)',
                marker=dict(size=12, color='rgba(231, 76, 60, 0)', line=dict(color='#e74c3c', width=2), symbol='circle'),
                hoverinfo='skip'
            ))
    else:
        fig.update_layout(title={'text': 'No Data Selected', 'x': 0.5})

    # Dragmode Persistence
    dragmode = 'zoom' 
    if current_fig_dict and 'layout' in current_fig_dict:
        dragmode = current_fig_dict['layout'].get('dragmode', 'zoom')
    if relayout_data and 'dragmode' in relayout_data:
        dragmode = relayout_data['dragmode']

    # Layout Styling
    fig.update_layout(
        title={'text': 'Margin Analysis', 'font': {'size': 20, 'color': '#2c3e50'}},
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis_title='Time (SFN.SLOT)',
        yaxis_title='Margin Value (us)',
        template='plotly_white',
        hovermode='closest',
        height=750,
        dragmode=dragmode,
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.1, bgcolor='#ecf0f1', bordercolor='#bdc3c7', borderwidth=1),
            gridcolor='#ecf0f1', zerolinecolor='#bdc3c7'
        ),
        yaxis=dict(autorange=True, fixedrange=False, domain=[0.2, 1], gridcolor='#ecf0f1'),
        yaxis2=dict(domain=[0, 0.15], range=[0, 1], visible=False, fixedrange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=80, b=40)
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#95a5a6")

    # ================= 視圖範圍邏輯 (嚴格的全覽控制) =================
    x_range = None
    y_range = None
    
    # 判斷是否為「使用者縮放」
    is_zoomed = False
    if relayout_data:
        if 'xaxis.range[0]' in relayout_data:
            x_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
            is_zoomed = True
        elif 'xaxis.range' in relayout_data:
            x_range = relayout_data['xaxis.range']
            is_zoomed = True
    
    # 若非使用者縮放，且之前有狀態，嘗試繼承（例如切換 Filter）
    # 但要排除「全覽狀態」的繼承，以免繼承到舊的局部
    if not is_zoomed and current_fig_dict and 'layout' in current_fig_dict and relayout_data is not None:
         # 只有在非首次載入時才繼承
         try:
            old_x = current_fig_dict['layout'].get('xaxis', {}).get('range', None)
            if old_x: x_range = old_x
         except:
            pass

    # ================= 應用邏輯 =================
    if x_range and not filtered_df.empty:
        # A. 縮放模式
        fig.update_layout(xaxis=dict(range=x_range, autorange=False)) # 明確關閉 autorange
        
        mask = (filtered_df['linear_x'] >= x_range[0]) & (filtered_df['linear_x'] <= x_range[1])
        view_df = filtered_df[mask]
        
        if not view_df.empty:
            y_min, y_max = view_df['m'].min(), view_df['m'].max()
            padding = (y_max - y_min) * 0.1 if y_max != y_min else 5
            padding = 5 if padding == 0 else padding
            y_range = [y_min - padding, y_max + padding]
            fig.update_layout(yaxis=dict(range=y_range, autorange=False))

        # 自適應標籤
        visible_count = len(view_df)
        if 0 < visible_count <= EXACT_TICK_THRESHOLD:
            precise_ticks = np.sort(view_df['linear_x'].unique())
            fig.update_layout(xaxis=dict(tickmode='array', tickvals=precise_ticks, ticktext=convert_linear_to_label(precise_ticks)))
        else:
            grid_ticks = np.linspace(x_range[0], x_range[1], 15, dtype=int)
            fig.update_layout(xaxis=dict(tickmode='array', tickvals=grid_ticks, ticktext=convert_linear_to_label(grid_ticks)))
            
    else:
        # B. 全覽模式 (預設) - 強制顯示所有點
        if not filtered_df.empty:
            # 取得全域範圍
            init_min, init_max = filtered_df['linear_x'].min(), filtered_df['linear_x'].max()
            
            # 手動計算範圍，不依賴 autorange
            range_span = init_max - init_min
            # 加上 2% 邊距
            padding = max(range_span * 0.02, 1) 
            final_range = [init_min - padding, init_max + padding]

            # 【關鍵】 強制寫入 range 並關閉 autorange，這樣 Plotly 就不會自作聰明縮放了
            fig.update_layout(xaxis=dict(range=final_range, autorange=False))
            
            # 全域均勻刻度
            grid_ticks = np.linspace(init_min, init_max, 15, dtype=int)
            fig.update_layout(xaxis=dict(tickmode='array', tickvals=grid_ticks, ticktext=convert_linear_to_label(grid_ticks)))

    return fig

if __name__ == '__main__':
    print("------------------------------------------------------------------")
    print(f"🚀 伺服器已啟動: http://{SERVER_HOST}:{SERVER_PORT}")
    print("------------------------------------------------------------------")
    app.run(debug=False, host=SERVER_HOST, port=SERVER_PORT)
