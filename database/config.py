from dotenv import load_dotenv
from pathlib import Path
import streamlit as st
import os

# 1. 嘗試讀取本地 .env 路徑
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

# 2. 定義一個智慧讀取函式（優先看 Streamlit Secrets，看不到再看本地 os.getenv）
def get_db_secret(key: str, default_val: str = None) -> str:
    # 使用 try...except 防止 secrets.toml 不存在時引發 Streamlit 系統崩潰
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except (FileNotFoundError, KeyError, RuntimeError, Exception):
        # 如果找不到 secrets 檔案或在非 Streamlit 環境下執行，直接忽略並往下走
        pass
    
    # 檢查是否在環境變數或 .env 中
    env_val = os.getenv(key)
    if env_val is not None:
        return env_val
        
    # 如果雲端、.env 都沒有，就回傳自訂的本地預設值
    return default_val


# 3. 統一讀取變數（在此處直接設定本地端預設值，例如 "127.0.0.1", "root"）
MYSQL_HOST = get_db_secret("MYSQL_HOST", default_val=os.getenv("MYSQL_HOST"))
MYSQL_ACCOUNT = get_db_secret("MYSQL_ACCOUNT",  default_val=os.getenv("MYSQL_ACCOUNT"))       
MYSQL_PASSWORD = get_db_secret("MYSQL_PASSWORD", default_val=os.getenv("MYSQL_PASSWORD")) 
MYSQL_DATABASE = get_db_secret("MYSQL_DATABASE", default_val=os.getenv("MYSQL_DATABASE"))

# 4. 處理 Port 的讀取與型態轉換（安全防呆）
raw_port = get_db_secret("MYSQL_PORT", default_val="3306")
MYSQL_PORT = int(raw_port) if raw_port and raw_port.isdigit() else 3306

# 5. 終極防呆驗證（這時候只有在連預設值都沒有設定到時才會觸發，基本上一定會通過）
if not all([MYSQL_HOST, MYSQL_ACCOUNT, MYSQL_PASSWORD, MYSQL_DATABASE]):
    raise ValueError(
        "【連線失敗】請確認 .env 檔案、Streamlit Secrets 或 config.py 中已設定基本連線資訊。"
    )