import os
import sys

# 1. 取得目前 app.py 檔案的絕對路徑
current_file = os.path.abspath(__file__)

# 2. 取得 app.py 所在的資料夾絕對路徑 (即 .../app)
current_dir = os.path.dirname(current_file)

# 3. 取得 app 資料夾的上一層，也就是真正的專案根目錄 (包含 database/, utils/ 的地方)
root_path = os.path.abspath(os.path.join(current_dir, ".."))

# 4. 終極清除干擾：如果 Python 把目前的 app/ 放在最前面，我們把它移到後面，把真正的 root_path 塞到 index 0
if current_dir in sys.path:
    sys.path.remove(current_dir)

# 確保根目錄永遠是第一優先搜尋順序
if root_path not in sys.path:
    sys.path.insert(0, root_path)
else:
    sys.path.remove(root_path)
    sys.path.insert(0, root_path)

import streamlit as st

# 必須是第一個 Streamlit 指令
st.set_page_config(layout="wide", page_title=None)

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

