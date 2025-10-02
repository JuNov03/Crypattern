# main_uv.py
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import ccxt
import uvicorn
from datetime import datetime, timedelta

# 거래소 연결
exchange = ccxt.binance()
pattern_len = 150
top_n = 3

# Dash 앱 초기화
app = dash.Dash(__name__)
app.title = "CRYPTO PATTERN DASHBOARD"

# 앱 레이아웃
app.layout = html.Div(
    style={"backgroundColor": "#111111", "color": "#FFFFFF", "font-family": "Oswald, sans-serif"},
    children=[
        html.H1("REAL-TIME BTC/USDT PATTERN DASHBOARD", style={"textTransform": "uppercase"}),
        dcc.Graph(id='live-graph', style={"height": "70vh"}),
        html.Div([
            html.Label("TIMEFRAME", style={"textTransform": "uppercase"}),
            dcc.Slider(
                id='timeframe-slider',
                min=0,
                max=6,
                marks={
                    0: '1m', 1: '5m', 2: '15m', 3: '30m', 4: '1h', 5: '5h', 6: '1d'
                },
                value=0,
                step=None
            ),
            html.Label("MAX BARS", style={"textTransform": "uppercase"}),
            dcc.Slider(
                id='max-bars-slider',
                min=10000,
                max=1000000,
                step=10000,
                value=100000,
                marks={
                    10000: '10k',
                    50000: '50k',
                    100000: '100k',
                    500000: '500k',
                    1000000: '1M'
                }
            )
        ], style={"padding": "20px"}),
        html.Div(id='info-div', style={"margin-top": "20px"})
    ]
)

# 시간 단위 매핑
timeframes = ['1m', '5m', '15m', '30m', '1h', '5h', '1d']

# OHLCV 데이터 불러오기
def fetch_ohlcv(symbol='BTC/USDT', timeframe='1m', limit=100000):
    all_data = []
    since = None
    fetch_size = 1000  # binance limit
    while True:
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=fetch_size, since=since)
            if len(candles) == 0:
                break
            all_data += candles
            since = candles[-1][0] + 1
            if len(all_data) >= limit:
                break
        except Exception as e:
            print(e)
            break
    df = pd.DataFrame(all_data[:limit], columns=['Timestamp','Open','High','Low','Close','Volume'])
    df['Date'] = pd.to_datetime(df['Timestamp'], unit='ms')
    return df

# 차트 생성
def create_figure(timeframe_idx, max_bars, top_n):
    timeframe = timeframes[timeframe_idx]
    df = fetch_ohlcv(limit=max_bars, timeframe=timeframe)
    if len(df) < pattern_len + 1:
        return go.Figure()

    recent_pattern = df['Close'].values[-pattern_len:]
    distances = []
    indices = []
    for start in range(len(df) - pattern_len):
        window = df['Close'].values[start:start + pattern_len]
        # 현재 패턴과 동일한 구간 제외
        if np.array_equal(window, recent_pattern):
            continue
        dist = np.linalg.norm(recent_pattern - window)
        distances.append(dist)
        indices.append(start)

    if len(distances) == 0:
        return go.Figure()

    top_indices = np.argsort(distances)[:top_n]

    fig = go.Figure()
    center = len(df) - 1

    # 현재 차트 (흰색)
    x_vals = np.arange(-pattern_len, 0)
    y_vals = recent_pattern
    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals, mode='lines', name='CURRENT', line=dict(color='white', width=3)
    ))

    # 과거 top n 패턴
    colors = ['red', 'green', 'blue', 'orange', 'purple']
    pattern_dates = []
    for i, idx in enumerate(top_indices):
        pattern = df['Close'].values[idx:idx + pattern_len]
        offset = recent_pattern[-1] - pattern[-1]
        y_pattern = pattern + offset
        x_pattern = np.arange(-pattern_len, 0)
        fig.add_trace(go.Scatter(
            x=x_pattern, y=y_pattern, mode='lines', name=f'PATTERN {i+1}',
            line=dict(color=colors[i % len(colors)], width=2, dash='dash')
        ))
        pattern_dates.append(df['Date'].iloc[idx].strftime('%Y-%m-%d %H:%M'))

    fig.update_layout(title='TOP N SIMILAR PATTERNS',
                      xaxis_title='Bars',
                      yaxis_title='Price',
                      plot_bgcolor="#111111",
                      paper_bgcolor="#111111",
                      font=dict(color="white", family="Oswald"))
    return fig, pattern_dates

# 콜백
@app.callback(
    [Output('live-graph', 'figure'),
     Output('info-div', 'children')],
    [Input('timeframe-slider', 'value'),
     Input('max-bars-slider', 'value')]
)
def update_graph(tf_idx, max_bars):
    fig, dates = create_figure(tf_idx, max_bars, top_n=3)
    info_text = "PATTERN DATES: " + ", ".join(dates) if dates else "NO PATTERNS FOUND"
    return fig, info_text

# 실행
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8050)
