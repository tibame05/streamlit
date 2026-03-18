import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta # 用於更精確的日期計算

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

# 將專案根目錄加入 sys.path
# 使用 insert(0, ...) 確保優先搜尋專案根目錄
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# backtest.py 檔案頂部
from database.db_connection import get_etf_list_by_region, get_etf_backtest_metrics, get_etf_prices


# 假設這些函式已在 db_connection.py 中
# from database.db_connection import get_etf_list_by_region, get_etf_backtest_metrics, get_etf_prices 

#st.set_page_config(page_title="投資模擬器", page_icon="💰", layout="wide")

st.title("💰 ETF 投資模擬器")
st.markdown("---")

# 設定映射：用於 UI 顯示與 DB 查詢/計算
PERIOD_MAP = {
    "1年": 1,
    "3年": 3,
    "10年": 10
}
PERIOD_LABEL_MAP = {
    "1年": "1y",
    "3年": "3y",
    "10年": "10y"
}

# ==============================
# 1. 側邊欄 - 篩選條件
# ==============================
# 側邊欄標題
st.sidebar.header("⚙️ 回測參數設定")

# 地區選擇
region = st.sidebar.selectbox("地區篩選", options=["TW", "US"], index=0)

with st.sidebar.form(key='backtest_form'):
    # ETF 代號篩選
    etf_list = get_etf_list_by_region(region)
    if etf_list:
        selected_etf_str = st.selectbox("ETF 代號篩選", options=etf_list)
        selected_etf_id = selected_etf_str.split(" ")[0]
    else:
        st.warning(f"查無 {region} 地區的 ETF 資料")
        st.stop()
        
    # 投資方式 (圖三樣式)
    investment_type = st.radio(
        "一次性 / 定期定額",
        options=["一次性投入", "定期定額"],
        index=0,
        horizontal=True
    )

    # 投資時間
    time_period = st.selectbox("投資時間", options=list(PERIOD_MAP.keys()), index=0)
    
    # 投入金額 (依地區變換貨幣)
    currency = "TWD" if region == "TW" else "USD"
    default_amount = 100000 if region == "TW" else 3000
    
    investment_amount = st.number_input(
        f"投入金額 ({currency})",
        min_value=1,
        value=default_amount,
        step=1000,
        format="%d"
    )
    
    # 必須使用 st.form_submit_button 才能提交表單
    submit_button = st.form_submit_button(
        label="💰 開始回測", 
        type="primary", 
        use_container_width=True
    )

# ==============================

# 判斷是否按下按鈕
if submit_button:
    # 將按鈕按下那一刻的所有參數存入 session_state
    st.session_state.run_backtest_metrics = True
    st.session_state.params = {
        'region': region,
        'selected_etf_id': selected_etf_str.split(" ")[0],
        'investment_type': investment_type,
        'time_period': time_period,
        'investment_amount': investment_amount,
        'currency': currency
    }
    
# ==============================
# 2. 回測核心邏輯與結果顯示
# ==============================

if st.session_state.get('run_backtest_metrics', False):
    
    period_label_db = PERIOD_LABEL_MAP[time_period]
    years = PERIOD_MAP[time_period]
    
    # 1. 獲取預先計算的指標
    with st.spinner(f"正在載入 {selected_etf_id} 的 {time_period} 指標..."):
        metrics = get_etf_backtest_metrics(selected_etf_id, period_label_db)

    if not metrics:
        st.error(f"⚠️ 找不到 {selected_etf_id} 在 {time_period} 期間的回測數據。")
        st.session_state.run_backtest_metrics = False
        st.stop()

    # 從資料庫指標中提取 CAGR
    cagr = metrics['cagr']
    
    # 2. 計算最終資產價值 (Final Value)
    
    if investment_type == "定期定額":
        st.warning("⚠️ **注意：** 由於資料庫指標 (CAGR) 適用於「一次性投入」，以下最終價值計算將忽略定期定額的投入時機，**僅基於 Lump Sum CAGR 進行粗略的年化估算**。實際定期定額績效應使用每日價格數據進行模擬。")
        
        # 估算總投入成本：每月投入金額 * 12個月 * 年數
        total_investment_cost = investment_amount * 12 * years
        
        # 粗略估算最終價值 (假設總投入成本全部在第一天投入，這是極度簡化)
        final_value = total_investment_cost * ((1 + cagr) ** years)
        
    else: # 一次性投入 (Lump Sum)
        total_investment_cost = investment_amount
        # 計算最終價值: FV = Amount * (1 + CAGR)^Years
        final_value = total_investment_cost * ((1 + cagr) ** years)

    
    # --- 最終結果計算與顯示 (圖二樣式) ---
    
    total_return_value = final_value - total_investment_cost
    return_pct_calc = (total_return_value / total_investment_cost) * 100
    
    st.markdown("### 🔑 最終價值估算結果")

    col1, col2, col3 = st.columns(3)

    col1.metric("總投入成本", f"{total_investment_cost:,.0f} {currency}")
    col2.metric("資產最終價值 (估算)", f"{final_value:,.0f} {currency}")
    
    # 總報酬率使用計算結果，並顯示絕對金額 Delta
    col3.metric("總報酬率 (估算)", f"{return_pct_calc:.2f}%", delta=f"{total_return_value:,.0f} {currency}")

    st.markdown("---")

    # --- 顯示預先計算的績效指標 (圖一指標部分) ---
    st.markdown(f"### 📊 {time_period} 績效指標 (基於資料庫回測結果)")
    
    # 確保資料庫中的總報酬率 (total_return) 是小數，需要 * 100 轉百分比
    db_total_return_pct = metrics['total_return'] * 100
    db_cagr_pct = metrics['cagr'] * 100
    db_volatility_pct = metrics['volatility'] * 100
    db_max_drawdown_pct = metrics['max_drawdown'] * 100 # Max Drawdown 通常是負值

    col4, col5, col6, col7 = st.columns(4)
    
    col4.metric("年化報酬率 (CAGR)", f"{db_cagr_pct:.2f}%")
    col5.metric("夏普比率 (Sharpe Ratio)", f"{metrics['sharpe_ratio']:.2f}")
    col6.metric("年化波動度", f"{db_volatility_pct:.2f}%")
    col7.metric("最大回撤 (Max Drawdown)", f"{db_max_drawdown_pct:.2f}%")

    st.markdown("---")

    # --- 繪製資產成長曲線 ---
    st.subheader("📈 資產與成本成長曲線")
    
    # 計算日期區間 (為了抓取股價繪圖)
    end_date = datetime.now().date()
    start_date = end_date - relativedelta(years=years)
    
    with st.spinner(f"正在載入 {selected_etf_id} 歷史股價以繪製圖表..."):
        price_df = get_etf_prices(selected_etf_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    if not price_df.empty:
        price_df = price_df.set_index("trade_date").sort_index()
        dates = price_df.index
        
        portfolio_history = []
        invested_history = []
        
        # --- 僅為了繪圖而執行的模擬邏輯 ---
        if investment_type == "一次性投入":
            initial_price = price_df.iloc[0]['adj_close']
            shares = investment_amount / initial_price
            portfolio_values = price_df['adj_close'] * shares
            portfolio_history = portfolio_values.values
            invested_history = [investment_amount] * len(dates)
            
        else: # 定期定額
            monthly_dates = price_df.resample("MS").first().index
            temp_df = price_df.copy()
            temp_df['shares_bought'] = 0.0
            temp_df['cash_flow'] = 0.0
            
            for m_date in monthly_dates:
                d = temp_df.index[temp_df.index >= m_date]
                if not d.empty:
                    invest_date = d[0]
                    price = temp_df.loc[invest_date, 'adj_close']
                    bought = investment_amount / price
                    temp_df.at[invest_date, 'shares_bought'] = bought
                    temp_df.at[invest_date, 'cash_flow'] = investment_amount
            
            temp_df['cum_shares'] = temp_df['shares_bought'].cumsum()
            temp_df['cum_invested'] = temp_df['cash_flow'].cumsum()
            temp_df['portfolio_value'] = temp_df['cum_shares'] * temp_df['adj_close']
            
            temp_df['portfolio_value'] = temp_df['portfolio_value'].fillna(0)
            temp_df['cum_invested'] = temp_df['cum_invested'].fillna(0)
    
            portfolio_history = temp_df['portfolio_value'].values
            invested_history = temp_df['cum_invested'].values
            
        # --- 繪圖 ---
        fig_wealth = go.Figure()
        
        # 資產價值線
        fig_wealth.add_trace(go.Scatter(
            x=dates, 
            y=portfolio_history, 
            mode='lines', 
            name='資產總值', 
            line=dict(color='#00CC96', width=2)
        ))
        
        # 投入成本線
        fig_wealth.add_trace(go.Scatter(
            x=dates, 
            y=invested_history, 
            mode='lines', 
            name='投入成本', 
            line=dict(color='#EF553B', dash='dash', width=2)
        ))
        
        fig_wealth.update_layout(
            title=f"<b>{selected_etf_id} 投資成長模擬 ({time_period})</b>",
            xaxis_title="日期",
            yaxis_title=f"金額 ({currency})",
            height=450,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        st.plotly_chart(fig_wealth, use_container_width=True)
    else:
        st.warning("⚠️ 無法取得詳細價格數據，無法繪製成長曲線。")
    
    # 重設狀態
    st.session_state.run_backtest_metrics = False

else:
    st.info("👈 請在左側選擇參數並點擊「💰 開始回測」")