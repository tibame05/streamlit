import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# 將專案根目錄加入 sys.path 以便匯入 modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.db_connection import get_etf_summary
from utils.log import get_logger

logger = get_logger(__name__)

def show_home():
    st.title("ETF 投資數據視覺化系統")

    st.markdown("""
    這是一個專為 ETF 投資者設計的工具，幫助您透過 **數據** 而非 **感覺** 來做決定。
    """)

    st.markdown("""
    您可以查看 **台股** 與 **美股** 的 ETF 的報酬率、波動度，並進行精準的投資模擬。
    """)

    st.markdown("### 🛠️ 快速操作指南")

    # 第一列：觀察與挑選
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.error("### 🔥 觀察")
        st.markdown("<span style='color: black; font-size: 1.0em;'>查看近兩週表現最亮眼與低迷的 ETF 快訊。</span>", unsafe_allow_html=True)
        st.page_link("views/analysis.py", label="👉 前往 **短期快訊**", icon="🔥")

    with row1_col2:
        st.info("### 1. 挑選")
        st.markdown("<span style='color: black; font-size: 1.0em;'>篩選出高報酬、高成交量、低波動率的長期標的。</span>", unsafe_allow_html=True)
        st.page_link("views/overview.py", label="👉 前往 **標的選擇**", icon="📊")

    st.markdown("<br>", unsafe_allow_html=True) # 增加一點列間距

    # 第二列：分析與模擬
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.success("### 2. 分析")
        st.markdown("<span style='color: black; font-size: 1.0em;'>透過 K 線圖與技術指標確認具體的進場時機。</span>", unsafe_allow_html=True)
        st.page_link("views/trend.py", label="👉 前往 **趨勢圖表**", icon="📈")

    with row2_col2:
        st.warning("### 3. 模擬")
        st.markdown("<span style='color: black; font-size: 1.0em;'>計算一次性投入或定期定額的預期最終獲利。</span>", unsafe_allow_html=True)
        st.page_link("views/simulator.py", label="👉 前往 **投資模擬器**", icon="💰")


# 執行主函式
show_home()