import streamlit as st

# 必須是第一個 Streamlit 指令
st.set_page_config(layout="wide")

# 定義頁面與對應的中標題
pages = {
    "導覽": [
        # 指向自己作為首頁
        st.Page("views/home.py", title="系統介紹", icon="🏠", default=True),
        st.Page("views/analysis.py", title="ETF 短期快訊", icon="🔥"),
        st.Page("views/overview.py", title="ETF 標的選擇", icon="📊"),
        st.Page("views/trend.py", title="價格與成交量趨勢", icon="📈"),
        st.Page("views/simulator.py", title="ETF 投資模擬器", icon="💰"),
    ]
}

pg = st.navigation(pages)
pg.run()

