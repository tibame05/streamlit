import streamlit as st
import pandas as pd
import plotly.express as px
from database.db_connection import get_etf_summary
from utils.log import get_logger

logger = get_logger(__name__)
st.set_page_config(page_title="ETF Dashboard", layout="wide")

df = get_etf_summary()

st.title("🏦 ETF 排行榜與風險報酬分析")
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
            text="etf_id"
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("無資料或資料庫尚未初始化。")
