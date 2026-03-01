import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# 將專案根目錄加入 sys.path
# 使用 insert(0, ...) 確保優先搜尋專案根目錄
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from database.db_connection import get_etf_overview
from utils.log import get_logger

logger = get_logger("overview")

st.set_page_config(page_title="ETF 標的選擇", page_icon="📊", layout="wide")

# 載入資料
df = get_etf_overview()

# 頁面標題
st.title("📊 ETF 標的選擇")

# 側邊欄 - 篩選條件
st.sidebar.header("🔍 篩選條件")

# ===== 1. 地區選擇 =====
st.sidebar.subheader("地區篩選")

region = st.sidebar.selectbox(
    "地區（單選）",
    options=["不限", "TW", "US"],
    index=1  # 預設選擇 TW
)
region_value = None if region == "不限" else region

# ===== 2. 時間範圍篩選 =====

st.sidebar.subheader("時間範圍篩選")

# 時間範圍選擇
time_period = st.sidebar.selectbox(
    "顯示時間範圍（單選）",
    options=["不限", "1年", "3年", "10年"],
    index=0,
    help="選擇要顯示的資料時間範圍"
)

# ===== 3. ETF 代號篩選 =====
st.sidebar.subheader("ETF 代號篩選")

# 先查詢所有 ETF 代號 (用於下拉選單)
@st.cache_data(ttl=3600)  # 快取1小時
def get_all_etf_ids(region=None, time_period="不限"): 
    """取得所有符合時間區間篩選條件的 ETF 代號"""
    df = get_etf_overview(region=region, time_period=time_period)
    if not df.empty:
        return sorted(df['ETF代號'].tolist())
    return []

# 取得 ETF 代號列表
all_etf_ids = get_all_etf_ids(region=region_value, time_period=time_period)

# 多選下拉選單 (可搜尋)
selected_etf_ids = st.sidebar.multiselect(
    "選擇 ETF 代號 (可多選)",
    options=all_etf_ids,
    default=None,
    placeholder="請選擇 ETF 代號 (可搜尋)",
    help="留空則顯示全部"
)

etf_ids = selected_etf_ids if selected_etf_ids else None

# ===== 4. 時間範圍篩選與 =====

# 根據時間範圍決定要顯示的欄位
if time_period == "不限":
    display_columns = [
        'ETF代號', 'ETF名稱', '管理費(%)', '成立日',
        '1年報酬率(%)', '3年報酬率(%)', '10年報酬率(%)',
        '1年波動度(%)', '3年波動度(%)', '10年波動度(%)',
        '1年成交量總和', '3年成交量總和', '10年成交量總和'
    ]
    sort_options = [
        "ETF代號", "管理費(%)", '成立日',
        "1年報酬率(%)", "3年報酬率(%)", "10年報酬率(%)",
        "1年波動度(%)", "3年波動度(%)", "10年波動度(%)",
        "1年成交量總和", "3年成交量總和", "10年成交量總和"
    ]
elif time_period == "1年":
    display_columns = [
        'ETF代號', 'ETF名稱', '管理費(%)', '成立日',
        '1年報酬率(%)', '1年波動度(%)', '1年成交量總和'
    ]
    sort_options = [
        "ETF代號", "管理費(%)", '成立日',
        "1年報酬率(%)", "1年波動度(%)", "1年成交量總和"
    ]
elif time_period == "3年":
    display_columns = [
        'ETF代號', 'ETF名稱', '管理費(%)', '成立日',
        '3年報酬率(%)', '3年波動度(%)', '3年成交量總和'
    ]
    sort_options = [
        "ETF代號", "管理費(%)", '成立日',
        "3年報酬率(%)", "3年波動度(%)", "3年成交量總和"
    ]
else:  # 10年
    display_columns = [
        'ETF代號', 'ETF名稱', '管理費(%)', '成立日',
        '10年報酬率(%)', '10年波動度(%)', '10年成交量總和'
    ]
    sort_options = [
        "ETF代號", "管理費(%)", '成立日',
        "10年報酬率(%)", "10年波動度(%)", "10年成交量總和"
    ]

# ===== 4. 排序選項 =====
st.sidebar.subheader("排序選項")

sort_by = st.sidebar.selectbox(
    "排序欄位",
    options=sort_options,
    index=0
)

ascending = st.sidebar.radio(
    "排序方式",
    options=["升序", "降序"],
    index=0
) == "升序"

# 查詢按鈕
st.sidebar.markdown("---")
if st.sidebar.button("🔄 查詢", type="primary", use_container_width=True):
    st.session_state['trigger_query'] = True
    st.session_state['time_period'] = time_period
    st.session_state['display_columns'] = display_columns

# 初始化查詢觸發器
if 'trigger_query' not in st.session_state:
    st.session_state['trigger_query'] = True
    st.session_state['time_period'] = time_period
    st.session_state['display_columns'] = display_columns

# 查詢資料
if st.session_state['trigger_query']:
    with st.spinner("🔄 正在從資料庫查詢..."):
        try:
            df = get_etf_overview(
                region=region_value,
                etf_ids=etf_ids,
                sort_by=sort_by,
                ascending=ascending,
                time_period=time_period
            )
            
            # 儲存到 session state
            st.session_state['df'] = df
            st.session_state['trigger_query'] = False
            
        except Exception as e:
            st.error(f"❌ 查詢失敗: {e}")
            st.session_state['df'] = pd.DataFrame()

# 顯示結果
st.markdown("---")
if 'df' in st.session_state and not st.session_state['df'].empty:
    df = st.session_state['df']
    display_columns = st.session_state.get('display_columns', df.columns.tolist())
    time_period = st.session_state.get('time_period', '不限')
    
    # 只顯示選擇的欄位
    df_display = df[display_columns]
    
    # 顯示表格
    st.subheader(f"📋 ETF 概覽資訊 (共 {len(df)} 檔 | 顯示範圍: {time_period})")
    
    # 建立顯示用的副本
    df_display = df[display_columns].copy()

    # 定義格式化邏輯
    target_format_cols = [
        '1年報酬率(%)', '3年報酬率(%)', '10年報酬率(%)',
        '1年波動度(%)', '3年波動度(%)', '10年波動度(%)'
    ]
    
    for col in target_format_cols:
        if col in df_display.columns:
            # 僅針對顯示副本進行字串轉換
            df_display[col] = pd.to_numeric(df_display[col], errors='coerce').map(
                lambda x: f"{x:.2f}%" if pd.notnull(x) else "-"
            )

    # 動態設定表格樣式
    column_config = {
        "ETF代號": st.column_config.TextColumn("ETF代號", width="small"),
        "ETF名稱": st.column_config.TextColumn("ETF名稱", width="medium"),
        "管理費(%)": st.column_config.NumberColumn("管理費(%)", format="%.2f%%", width="small"),
        "成立日": st.column_config.DateColumn("成立日", format="YYYY-MM-DD", width="small"),
    }
    
    # 根據顯示欄位動態加入配置
    for col in display_columns:
        if "成交量" in col:
            column_config[col] = st.column_config.NumberColumn(col, format="%d", width="medium")
        elif "報酬率" in col or "波動度" in col:
            column_config[col] = st.column_config.TextColumn(col, width="small")
    
    # 顯示表格 (使用副本)
    st.dataframe(
        df_display,
        use_container_width=True,
        height=600,
        column_config=column_config,
        hide_index=True
    )
    
    # 下載按鈕
    csv = df_display.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 下載 CSV",
        data=csv,
        file_name=f"etf_overview_{time_period}.csv",
        mime="text/csv",
        use_container_width=True
    )

    st.markdown("---")

    # [修改] 詳細統計：改為顯示各項指標之最 (圖二的部分)
    with st.expander("🏆 查看各項指標之最 (詳細統計)", expanded=True):
        
        # 輔助函式：取得特定欄位的最佳 ETF
        def get_best_etf_info(dataframe, col_name, method='max'):
            """
            Args:
                dataframe: 資料表
                col_name: 要比較的欄位名稱
                method: 'max' 取最大值, 'min' 取最小值
            Returns:
                str: 格式化的字串 "代號 名稱 (數值)"
            """
            # 1. 基本檢查
            if dataframe.empty or col_name not in dataframe.columns:
                return "無資料"
            
            try:
                # 2. 【關鍵修正】確保該欄位是數值型態 (處理可能混入的字串或 None)
                # 使用 errors='coerce' 將無法轉數字的變成 NaN，避免報錯
                series = pd.to_numeric(dataframe[col_name], errors='coerce')
                
                # 3. 尋找最大/最小值的 "索引標籤 (Index Label)"
                if method == 'max':
                    idx = series.idxmax()
                else:
                    idx = series.idxmin()
                
                # 如果整欄都是 NaN，idx 會是 NaN
                if pd.isna(idx):
                    return "無有效數值"

                # 4. 【關鍵修正】使用 .loc[idx] 而不是 .iloc[idx]
                # 因為 idxmax 回傳的是索引標籤，必須用 loc 定位
                row = dataframe.loc[idx]
                val = row[col_name]
                
                # 5. 數值格式化 (加入錯誤處理以免 val 為 None)
                if pd.isna(val):
                    return "數值為空"

                if "報酬率" in col_name or "波動度" in col_name or "管理費" in col_name:
                    val_str = f"{float(val):.2f}%"
                elif "成交量" in col_name:
                    val_str = f"{int(val):,}" # 加千分位
                else:
                    val_str = str(val)
                
                return f"**{row['ETF代號']} {row['ETF名稱']}**\n\n {val_str}"

            except Exception as e:
                # 顯示具體錯誤原因，方便除錯 (例如: KeyError, TypeError)
                return f"錯誤: {str(e)}"

        # 定義要顯示的時間區段
        if time_period == "不限":
            periods = ["1年", "3年", "10年"]
        else:
            periods = [time_period] # 例如 ["1年"]

        # 版面配置：4欄 (管理費, 成交量, 報酬率, 波動度)
        col1, col2, col3, col4 = st.columns(4)
        
        # --- 1. 管理費 (永遠顯示) ---
        with col1:
            st.markdown("#### 💰 最低管理費")
            st.info(get_best_etf_info(df, "管理費(%)", method='min'))

        # --- 2. 成交量 ---
        with col2:
            st.markdown("#### 📊 最高成交量")
            for p in periods:
                label = f"{p}最高成交量"
                col_target = f"{p}成交量總和"
                st.markdown(f"**{p}**")
                st.success(get_best_etf_info(df, col_target, method='max'))

        # --- 3. 報酬率 ---
        with col3:
            st.markdown("#### 🚀 最高報酬率")
            for p in periods:
                col_target = f"{p}報酬率(%)"
                st.markdown(f"**{p}**")
                # 使用 error 顏色 (紅色) 代表高報酬通常比較顯眼，或維持預設
                st.error(get_best_etf_info(df, col_target, method='max'))

        # --- 4. 波動度 ---
        with col4:
            st.markdown("#### 🛡️ 最低波動度")
            for p in periods:
                col_target = f"{p}波動度(%)"
                st.markdown(f"**{p}**")
                st.warning(get_best_etf_info(df, col_target, method='min'))

    st.markdown("---")

    # ===== 新增：風險與報酬氣泡圖 =====
    st.subheader("🫧 風險與報酬氣泡圖")
    
    # 準備繪圖資料
    if not df.empty:
        # 1. 決定要畫哪一個時間區段的資料
        # 若側邊欄選 "不限"，依據您的需求預設使用 "10年" 資料
        if time_period == "不限":
            target_period = "10年"
        else:
            target_period = time_period

        # 2. 定義對應的欄位名稱
        col_x = f"{target_period}波動度(%)"
        col_y = f"{target_period}報酬率(%)"
        col_size = f"{target_period}成交量總和"
        
        # 3. 檢查欄位是否存在 (安全防護)
        if col_x in df.columns and col_y in df.columns:
            # 複製一份資料作繪圖用，移除空值以免報錯
            chart_df = df.dropna(subset=[col_x, col_y]).copy()
            
            # --- [關鍵修改] 資料清洗與百分比換算 ---
            # 1. 先確保成交量欄位轉為純數字 (移除逗號，處理字串)
            chart_df[col_size] = (
                chart_df[col_size]
                .astype(str)                # 先轉字串確保 replace 可用
                .str.replace(',', '')       # 移除千分位逗號
            )
            chart_df[col_size] = pd.to_numeric(chart_df[col_size], errors='coerce').fillna(0)

            # 2. 計算百分比 (建立新欄位用於 size，原欄位保留用於 hover 顯示數值)
            max_vol = chart_df[col_size].max()
            if max_vol > 0:
                chart_df['size_scaled'] = (chart_df[col_size] / max_vol) * 100
            else:
                chart_df['size_scaled'] = 0
            # -------------------------------------

            # 4. 建立 Plotly 氣泡圖
            if not chart_df.empty:
                fig = px.scatter(
                    chart_df,
                    x=col_x,
                    y=col_y,
                    size='size_scaled',     # [修改] 使用換算後的百分比欄位控制大小
                    color="ETF代號",        # 顏色區分
                    hover_name="ETF名稱",
                    hover_data={
                        "ETF代號": True,
                        'size_scaled': False, # 隱藏百分比欄位
                        col_x: True, 
                        col_y: True, 
                        col_size: True        # 顯示原本的成交量數值
                    },
                    text="ETF代號",         # 顯示代號標籤
                    title=f"<b>ETF 風險與報酬分析 ({target_period})</b>",
                    labels={
                        col_x: "波動度 (風險) %",
                        col_y: "年化報酬率 %",
                        col_size: "成交量",
                        "ETF代號": "代號"
                    },
                    size_max=60             # 限制氣泡最大尺寸
                )
                
                # 優化圖表樣式
                fig.update_traces(
                    textposition='top center',
                    marker=dict(opacity=0.8, line=dict(width=1, color='DarkSlateGrey'))
                )
                
                # 設定軸線與背景
                fig.update_layout(
                    height=600,
                    xaxis_title="波動度 (越低越好) ⭠",
                    yaxis_title="年化報酬率 (越高越好) ⭢",
                    showlegend=True,
                    legend_title_text='ETF 代號'
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"⚠️ 在此篩選條件下，無足夠的 {target_period} 數據可繪製氣泡圖。")
        else:
            st.error("❌ 無法繪製圖表：找不到對應的欄位數據。")

# (以下接回原本的 elif 'df' in st.session_state ... 程式碼)

elif 'df' in st.session_state and st.session_state['df'].empty:
    st.warning("⚠️ 查無符合條件的資料")

else:
    st.info("👈 請在左側設定篩選條件,然後點擊「查詢」按鈕")
