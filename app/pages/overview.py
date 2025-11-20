import streamlit as st
import pandas as pd
import plotly.express as px
from database.db_connection import get_etf_summary
from utils.log import get_logger

logger = get_logger("overview")

st.set_page_config(page_title="ETF 總覽", page_icon="📊", layout="wide")

# 載入資料
df = get_etf_summary()

# 頁面標題
st.title("📊 ETF 總覽與分析")

if not df.empty:
    # 側邊欄篩選
    st.sidebar.header("篩選條件")
    
    # 區域篩選
    regions = ["全部"] + sorted(df["region"].dropna().unique().tolist())
    selected_region = st.sidebar.selectbox("選擇區域", regions)
    
    if selected_region != "全部":
        df = df[df["region"] == selected_region]
    
    # 顯示統計資訊
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("ETF 總數", len(df))
    with col2:
        avg_return = df["annual_return_3y"].mean()
        st.metric("平均年化報酬 (3Y)", f"{avg_return:.2f}%")
    with col3:
        avg_volatility = df["volatility_3y"].mean()
        st.metric("平均波動度 (3Y)", f"{avg_volatility:.2f}%")
    
    # 排行榜
    st.subheader("📈 ETF 排行榜")
    
    # 選擇排序欄位
    sort_options = {
        "成交量": "volume",
        "年化報酬 (3Y)": "annual_return_3y",
        "波動度 (3Y)": "volatility_3y",
        "費用率": "expense_ratio"
    }
    sort_by = st.selectbox("排序依據", list(sort_options.keys()))
    sort_col = sort_options[sort_by]
    
    # 排序並顯示
    df_sorted = df.sort_values(by=sort_col, ascending=False)
    st.dataframe(
        df_sorted,
        use_container_width=True,
        hide_index=True
    )
    
    # 風險報酬散點圖
    st.subheader("📊 風險報酬散點圖")
    
    fig = px.scatter(
        df,
        x="volatility_3y",
        y="annual_return_3y",
        size="volume",
        color="region",
        hover_name="name",
        hover_data={
            "etf_id": True,
            "expense_ratio": ":.2f",
            "volume": ":,.0f"
        },
        labels={
            "volatility_3y": "波動度 (3Y, %)",
            "annual_return_3y": "年化報酬 (3Y, %)",
            "region": "區域"
        },
        title="ETF 風險報酬分布"
    )
    
    fig.update_layout(
        height=600,
        hovermode="closest"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
else:
    st.warning("⚠️ 無資料或資料庫尚未初始化。")
    st.info("請確認資料庫連線正常，並已匯入 ETF 資料。")
