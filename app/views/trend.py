import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

import sys
import os

# 設定頁面樣式：移除表單邊框
st.markdown(
    """
    <style>
    [data-testid="stForm"] {
        border: none;
        padding: 0;
        background-color: transparent;
        box-shadow: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 使用 insert(0, ...) 確保優先搜尋專案根目錄
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# 引用您剛剛建立的 db_connection 函式
from database.db_connection import get_etf_kline_data, get_etf_list_by_region

# 分頁標題
#st.set_page_config(page_title="價格與成交量趨勢", page_icon="📈", layout="wide")
st.html(f"<script>parent.document.title = '價格與成交量趨勢'</script>")


st.title("📈 價格與成交量趨勢圖")
st.markdown("---")

# ==============================
# 1. 側邊欄篩選條件
# ==============================
st.sidebar.header("🔍 篩選條件")

# --- 地區篩選 ---
region_option = st.sidebar.selectbox(
    "地區篩選",
    options=["TW", "US"],
    index=0
)

with st.sidebar.form(key='trend_filter_form'):
    # --- ETF 代號篩選 (根據地區連動) ---
    # 取得該地區的 ETF 列表
    etf_list = get_etf_list_by_region(region_option)

    if etf_list:
        selected_etf_str = st.selectbox(
            "ETF 代號篩選",
            options=etf_list
        )
        # 從字串 "0050 元大台灣50" 中取出 "0050"
        selected_etf_id = selected_etf_str.split(" ")[0]
    else:
        st.warning(f"查無 {region_option} 地區的 ETF 資料")
        st.stop()

    # --- 時間尺度篩選 ---
    time_scale = st.selectbox(
        "時間尺度",
        options=["日 (Daily)", "週 (Weekly)", "月 (Monthly)"],
        index=0
    )

    # --- 日期範圍選擇 ---
    # 預設看近一年的資料
    default_start = datetime.today() - timedelta(days=365)
    default_end = datetime.today()

    col1, col2 = st.columns(2)
    start_date = col1.date_input("開始日期", default_start).strftime("%Y-%m-%d")
    end_date = col2.date_input("結束日期", default_end).strftime("%Y-%m-%d")

    # --- 提交按鈕 ---
    submit_button = st.form_submit_button("📈 繪製圖表", type="primary", width="stretch")

# ==============================
# 2. 資料讀取與處理
# ==============================

if submit_button:
    # 轉換日期格式
    selected_etf_id = selected_etf_str.split(" ")[0]
    with st.spinner("正在讀取與處理資料..."):
        # 從資料庫讀取原始日資料
        raw_df = get_etf_kline_data(selected_etf_id, start_date, end_date)
        
        if raw_df.empty:
            st.error(f"⚠️ 找不到 {selected_etf_id} 在指定期間的資料。")
        else:
            # 設定 trade_date 為索引，方便 resample
            df = raw_df.set_index("trade_date").sort_index()

            # --- 根據時間尺度進行資料聚合 (Resample) ---
            if "週" in time_scale:
                # 'W-FRI' 代表每週以週五結算，符合「每週最後一天營業日」的概念
                # 邏輯：開盤取第一天，收盤取最後一天，最高取期間最大，最低取期間最小，成交量加總
                df_resampled = df.resample('W-FRI').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                })
            elif "月" in time_scale:
                # 'M' 代表月底結算
                df_resampled = df.resample('ME').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                })
            else:
                # 日資料不需處理
                df_resampled = df

            # 移除因為 resample 可能產生的空值列 (例如連假期間)
            df_final = df_resampled.dropna()

            # 確保 df_final.index 仍然是 datetime 才能使用 strftime
            if not isinstance(df_final.index, pd.DatetimeIndex):
                df_final.index = pd.to_datetime(df_final.index)

            # 這是為了讓 X 軸變成「類別」型態，從而消除週末與假日的空白
            df_final.index = df_final.index.strftime('%Y-%m-%d')

            # ==============================
            # 3. 繪製 Plotly 圖表
            # ==============================
            
            # 建立子圖：上圖為 K 線，下圖為成交量 (共用 X 軸)
            fig = make_subplots(
                rows=2, cols=1, 
                shared_xaxes=True, 
                vertical_spacing=0.03, 
                row_heights=[0.7, 0.3], # K線圖佔 70%，成交量佔 30%
                specs=[[{"secondary_y": True}], [{"secondary_y": False}]] # 上圖啟用雙 Y 軸(可選)
            )

            # --- A. 繪製 K 線圖 (Candlestick) ---
            # 台灣股市習慣：紅漲綠跌 (increasing=red, decreasing=green)
            # 美股習慣相反，這裡示範台股習慣，您可依需求調整
            colors = dict(increasing_line_color='#ef5350', decreasing_line_color='#26a69a')
            
            # 建立 hover text
            hover_text = [
                f"高: {h:.2f}<br>低: {l:.2f}<br>開: {o:.2f}<br>收: {c:.2f}"
                for h, l, o, c in zip(df_final['high'], df_final['low'], df_final['open'], df_final['close'])
            ]

            fig.add_trace(
                go.Candlestick(
                    x=df_final.index,
                    open=df_final['open'],
                    high=df_final['high'],
                    low=df_final['low'],
                    close=df_final['close'],
                    name='K 線',
                    increasing=dict(line=dict(color=colors['increasing_line_color'])),
                    decreasing=dict(line=dict(color=colors['decreasing_line_color'])),
                    text=hover_text,
                    hoverinfo='text'
                ),
                row=1, col=1
            )

            # --- B. 加入移動平均線 (MA) - 模仿 MoneyDJ 風格 ---
            # 只有在「日」尺度下顯示 MA 比較合理，或者週月也可以算
            ma_days = [5, 20, 60]
            ma_colors = ['#1f77b4', '#ff7f0e', '#9467bd'] # 藍, 橘, 紫
            
            for i, days in enumerate(ma_days):
                ma_value = df_final['close'].rolling(window=days).mean()
                
                fig.add_trace(
                    go.Scatter(
                        x=df_final.index, 
                        y=ma_value, 
                        mode='lines', 
                        name=f'MA{days}',
                        line=dict(width=1, color=ma_colors[i]),
                        hovertemplate=f"MA{days}: %{{y:.2f}}<extra></extra>"
                    ),
                    row=1, col=1
                )

            # --- C. 繪製成交量圖 (Bar) ---
            # 設定成交量顏色：收紅(漲)為紅柱，收綠(跌)為綠柱
            vol_colors = [
                colors['increasing_line_color'] if c >= o else colors['decreasing_line_color']
                for c, o in zip(df_final['close'], df_final['open'])
            ]

            fig.add_trace(
                go.Bar(
                    x=df_final.index,
                    y=df_final['volume'],
                    name='成交量',
                    marker_color=vol_colors,
                    hovertemplate="成交量: %{y:,}<extra></extra>"
                ),
                row=2, col=1
            )

            # --- D. 圖表版面設定 ---
            title_text = f"{selected_etf_str} - {time_scale} 趨勢圖"
            
            # 顯示最新數據摘要 (類似 MoneyDJ 頂部資訊)
            last_rec = df_final.iloc[-1]
            prev_rec = df_final.iloc[-2] if len(df_final) > 1 else last_rec
            change = last_rec['close'] - prev_rec['close']
            pct_change = (change / prev_rec['close']) * 100
            
            color_class = "red" if change > 0 else "green" if change < 0 else "gray"
            
            st.markdown(f"""
            <div style="display: flex; gap: 20px; align-items: baseline; margin-bottom: 10px;">
                <h2 style="margin:0;">{last_rec['close']:.2f}</h2>
                <span style="color: {color_class}; font-size: 1.2em; font-weight: bold;">
                    {'▲' if change > 0 else '▼' if change < 0 else '-'} {abs(change):.2f} ({pct_change:.2f}%)
                </span>
                <span style="color: gray;">成交量: {int(last_rec['volume']):,}</span>
                <span style="color: gray;">日期: {pd.to_datetime(last_rec.name).strftime('%Y-%m-%d')}</span>

            </div>
            """, unsafe_allow_html=True)

            # 圖表整體設定
            fig.update_layout(
                title=title_text,
                xaxis_rangeslider_visible=False, # 隱藏底部的範圍滑桿 (為了美觀)
                height=600,
                hovermode='x', 
                yaxis_title="價格",
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    xanchor="right", 
                    x=1
                )
            )
            
            # 設定 X 軸為「類別 (category)」以消除空隙
            # tickmode='auto' 與 nticks 讓它自動減少顯示的日期標籤，避免全部擠在一起
            fig.update_xaxes(
                type='category', 
                tickmode='auto', 
                nticks=20,
                row=1, col=1
            )
            
            # 因為是 shared_xaxes，下方子圖的 X 軸也要設
            fig.update_xaxes(
                type='category', 
                tickmode='auto', 
                nticks=20,
                row=2, col=1
            )

            # 設定 Y 軸標籤
            fig.update_yaxes(title_text="價格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=2, col=1)

            # 顯示圖表
            st.plotly_chart(fig, width="stretch")

else:
    st.info("👈 請在左側選擇條件並點擊「📈 繪製圖表」")