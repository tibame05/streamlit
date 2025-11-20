import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from database.db_connection import get_active_etfs, get_etf_prices
from utils.log import get_logger

logger = get_logger("simulator")

st.set_page_config(page_title="投資模擬器", page_icon="💰", layout="wide")

# 頁面標題
st.title("💰 ETF 投資模擬器")
st.markdown("模擬定期定額投資策略，計算報酬率與累積資產。")

# 載入 ETF 清單
etf_list = get_active_etfs()

if not etf_list.empty:
    # 側邊欄設定
    st.sidebar.header("模擬參數設定")
    
    # 選擇 ETF
    etf_options = {f"{row['name']} ({row['etf_id']})": row['etf_id'] 
                   for _, row in etf_list.iterrows()}
    selected_etf_name = st.sidebar.selectbox("選擇 ETF", list(etf_options.keys()))
    selected_etf_id = etf_options[selected_etf_name]
    
    # 投資期間
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "開始日期",
            value=datetime.now() - timedelta(days=365*3)
        )
    with col2:
        end_date = st.date_input(
            "結束日期",
            value=datetime.now()
        )
    
    # 投資金額
    monthly_investment = st.sidebar.number_input(
        "每月投資金額 (USD)",
        min_value=100,
        max_value=100000,
        value=1000,
        step=100
    )
    
    # 執行模擬按鈕
    if st.sidebar.button("🚀 開始模擬", type="primary"):
        # 載入價格資料
        price_data = get_etf_prices(
            selected_etf_id,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )
        
        if not price_data.empty:
            # 模擬定期定額投資
            price_data = price_data.set_index("trade_date")
            
            # 計算每月第一個交易日
            monthly_dates = price_data.resample("MS").first().index
            
            # 初始化
            total_invested = 0
            total_shares = 0
            portfolio_value = []
            investment_dates = []
            
            for date in monthly_dates:
                if date in price_data.index:
                    price = price_data.loc[date, "adj_close"]
                    shares = monthly_investment / price
                    total_shares += shares
                    total_invested += monthly_investment
                    
                    # 記錄投資組合價值
                    current_value = total_shares * price
                    portfolio_value.append(current_value)
                    investment_dates.append(date)
            
            # 計算最終價值
            final_price = price_data.iloc[-1]["adj_close"]
            final_value = total_shares * final_price
            total_return = final_value - total_invested
            return_rate = (total_return / total_invested * 100) if total_invested > 0 else 0
            
            # 顯示結果
            st.success("✅ 模擬完成！")
            
            # 關鍵指標
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("總投資金額", f"${total_invested:,.0f}")
            with col2:
                st.metric("最終資產價值", f"${final_value:,.0f}")
            with col3:
                st.metric("總報酬", f"${total_return:,.0f}")
            with col4:
                st.metric("報酬率", f"{return_rate:.2f}%")
            
            # 繪製資產成長圖
            st.subheader("📈 資產成長曲線")
            
            fig = go.Figure()
            
            # 投資組合價值
            fig.add_trace(go.Scatter(
                x=investment_dates,
                y=portfolio_value,
                mode="lines",
                name="投資組合價值",
                line=dict(color="blue", width=2)
            ))
            
            # 累積投資金額
            cumulative_investment = [monthly_investment * (i + 1) for i in range(len(investment_dates))]
            fig.add_trace(go.Scatter(
                x=investment_dates,
                y=cumulative_investment,
                mode="lines",
                name="累積投資金額",
                line=dict(color="gray", width=2, dash="dash")
            ))
            
            fig.update_layout(
                xaxis_title="日期",
                yaxis_title="金額 (USD)",
                hovermode="x unified",
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 詳細資訊
            with st.expander("📊 詳細投資記錄"):
                investment_log = pd.DataFrame({
                    "投資日期": investment_dates,
                    "投資金額": [monthly_investment] * len(investment_dates),
                    "投資組合價值": portfolio_value
                })
                st.dataframe(investment_log, use_container_width=True, hide_index=True)
        else:
            st.error("❌ 無法載入價格資料，請檢查日期範圍或 ETF 代碼。")
else:
    st.warning("⚠️ 無法載入 ETF 清單，請檢查資料庫連線。")
