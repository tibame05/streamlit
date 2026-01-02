# 🚀 《ETF Dashboard — Streamlit 專案實作與部署指南（進階版）》

## 🎯 專案定位

| 項目   | 狀態                                    |
| ---- | ------------------------------------- |
| 架構   | Streamlit + MySQL + Docker（不使用 Nginx） |
| 執行環境 | GCP VM（內部或測試用）                        |
| 套件管理 | Pipenv（取代 requirements.txt）           |
| 功能模組 | 資料庫層（database）、分析邏輯層（utils）、視覺化層（app） |
| 目標   | 模組化、可維護、支援互動式 ETF 視覺化與運算              |

---

## 🧱 1️⃣ 專案結構設計

```
etf-dashboard/
├── Pipfile
├── Pipfile.lock
├── .env
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── app/
│   ├── app.py
│   ├── __init__.py
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── overview.py         # ETF 標的選擇
│   │   ├── simulator.py        # ETF 投資模擬器
│   │   └── trend.py            # 價格與成交量趨勢圖
│   ├── .streamlit/
│   │   └── secrets.toml
├── database/
│   ├── __init__.py
│   ├── db_connection.py         # SQLAlchemy engine + connect()
│   ├── queries.py               # 預先定義查詢語句
├── utils/
│   ├── __init__.py
│   ├── etf_calculations.py      # 指標計算、報酬率、風險
│   ├── log.py                   # logging 設定
├── README.md
└── tests/
    ├── test_db_connection.py
    ├── test_etf_calculations.py
```

---

## 🔐 2️⃣ 環境設定

### `.env`

```bash
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=etfuser
MYSQL_PASSWORD=StrongPassword
MYSQL_DB=etf_db
STREAMLIT_SERVER_PORT=8501
LOG_LEVEL=INFO
```

### `.streamlit/secrets.toml`

```toml
[connections.mydb]
url = "mysql+pymysql://etfuser:StrongPassword@mysql:3306/etf_db"
```

---

## 🧩 3️⃣ 資料庫層 — `database/db_connection.py`

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_engine():
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    host = os.getenv("MYSQL_HOST")
    db = os.getenv("MYSQL_DB")
    url = f"mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600)

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

---

## 🧠 4️⃣ 分析層 — `utils/etf_calculations.py`

```python
import pandas as pd
import numpy as np

def calc_portfolio_metrics(df):
    """
        計算年化報酬、波動度與夏普比率

        parameters:
            df (pd.DataFrame): 含每日報酬率的資料

        returns:
            dict: {'annual_return': float, 'volatility': float, 'sharpe': float}
    """
    mean_daily = df['returns'].mean()
    std_daily = df['returns'].std()
    annual_return = (1 + mean_daily) ** 252 - 1
    volatility = std_daily * (252 ** 0.5)
    sharpe = (annual_return - 0.02) / volatility if volatility else 0
    return {
        "annual_return": round(annual_return * 100, 2),
        "volatility": round(volatility * 100, 2),
        "sharpe": round(sharpe, 2)
    }
```

---

## 🧾 5️⃣ Logging 模組 — `utils/log.py`

```python
import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.FileHandler(f"{LOG_DIR}/app.log", encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(LOG_LEVEL)
    return logger
```

---

## 🧭 6️⃣ Streamlit 主程式 — `app/app.py`

```python
import streamlit as st
import pandas as pd
import plotly.express as px
from database.db_connection import engine
from utils.log import get_logger

logger = get_logger(__name__)
st.set_page_config(page_title="ETF Dashboard", layout="wide")

@st.cache_data(ttl=300)
def load_etf_data():
    query = "SELECT etf_id, name, expense_ratio, inception_date, volume, annual_return_3y, volatility_3y FROM etf_summary"
    return pd.read_sql(query, engine)

df = load_etf_data()

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
```

---

## 🐳 7️⃣ Docker 與部署設定

### `docker/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv && pipenv install --system --deploy

COPY app/ ./app/
COPY database/ ./database/
COPY utils/ ./utils/
EXPOSE 8501

CMD ["streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
```

---

### `docker/docker-compose.yml`

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: etf_db
      MYSQL_USER: etfuser
      MYSQL_PASSWORD: StrongPassword
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql

  streamlit:
    build: ..
    env_file:
      - ../.env
    ports:
      - "8501:8501"
    depends_on:
      - mysql
    volumes:
      - ../app:/app
      - ../utils:/utils
      - ../database:/database

volumes:
  mysql_data:
```

---

## ☁️ 8️⃣ 在 GCP VM 啟動

```bash
cd etf-dashboard/docker
sudo docker compose up -d
```

* 開啟 VM 防火牆：允許 TCP 8501
* 進入 `http://<VM_IP>:8501`
* 嵌入 Google Sites：使用 `<iframe src="http://<VM_IP>:8501" width="100%" height="800"></iframe>`

---

## ✅ 最佳實踐摘要

| 類別   | 工具                 | 說明            |
| ---- | ------------------ | ------------- |
| 環境管理 | Pipenv             | 確保依賴版本一致      |
| 資料庫  | SQLAlchemy         | 安全、可移植        |
| 日誌   | Python logging     | 自動寫入檔案，方便除錯   |
| 視覺化  | Plotly + Streamlit | 可互動、嵌入性佳      |
| 部署   | Docker Compose     | 無需 Nginx，簡單快速 |


