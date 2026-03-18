import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# 將專案根目錄加入 sys.path 以便匯入 modules
# 使用 insert(0, ...) 確保優先搜尋專案根目錄
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_connection import get_etf_summary
from utils.log import get_logger

logger = get_logger(__name__)
#st.set_page_config(page_title="首頁", page_icon="🏠", layout="wide")

df = get_etf_summary()

st.title("🏠 ETF 排行榜與風險報酬分析")
if not df.empty:
    with st.expander("📈 排行榜"):
        st.dataframe(df)

    with st.expander("📊 風險報酬散點圖"):
        fig = px.scatter(
            df,
            x="volatility_3y",
            y="annual_return_3y",
            size="volume",
            hover_name="name",
            text="etf_id",
            labels={
                "volatility_3y": "年化波動度 (%)",
                "annual_return_3y": "年化報酬率 (%)",
                "volume": "成交量",
                "name": "ETF 名稱",
                "etf_id": "代號"
            }
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("無資料或資料庫尚未初始化。")
