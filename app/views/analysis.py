import streamlit as st
import pandas as pd
from database.db_connection import get_short_term_momentum

def show_momentum_analysis():
    st.markdown("# **🔥 ETF 短期動能快訊 (近兩週)**")

    # --- 新增視覺說明區塊 ---
    with st.expander("💡 數據顏色說明", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**10日報酬 (累積損益)**")
            st.markdown("- <span style='color:red'>紅色</span>：上漲", unsafe_allow_html=True)
            st.markdown("- <span style='color:green'>綠色</span>：下跌", unsafe_allow_html=True)
            st.markdown("- **加粗**：波動劇烈 (> 5%)", unsafe_allow_html=True)
        with c2:
            st.markdown("**日均波動 (風險警示)**")
            st.markdown("- <span style='color:blue'>藍色</span>：低波動 (< 0.5%)", unsafe_allow_html=True)
            st.markdown("- <span style='color:black'>黑色</span>：正常範圍", unsafe_allow_html=True)
            st.markdown("- <span style='color:purple'>紫色</span>：高波動 (> 1.2%)", unsafe_allow_html=True)
        with c3:
            st.markdown("**勝率 (趨勢連續性)**")
            st.markdown("- **進度條**：越長代表上漲天數越多", unsafe_allow_html=True)
            st.markdown("- **指標**：超過 70% 代表極強勢", unsafe_allow_html=True)
    
    tab_tw, tab_us = st.tabs(["🇹🇼 台股 ETF", "🇺🇸 美股 ETF"])
    
    with tab_tw:
        display_momentum_tables(region="TW")
        
    with tab_us:
        display_momentum_tables(region="US")

def style_momentum_df(df, region):
    """
    實作進階視覺化邏輯
    """
    def color_return(val):
        # 報酬率：台股習慣紅漲綠跌，絕對值 > 5% 加粗
        color = 'red' if val > 0 else 'green' if val < 0 else 'black'
        weight = 'bold' if abs(val) > 5 else 'normal'
        return f'color: {color}; font-weight: {weight};'

    def color_volatility(val):
        # 波動度顏色邏輯：
        # 低波動 < 0.5%：藍色
        # 正常 0.6% ~ 1.1%：黑色
        # 高波動 > 1.2%：紫色
        if val < 0.5:
            return 'color: blue;'
        elif val > 1.2:
            return 'color: purple;'
        else:
            return 'color: black;'

    # 建立 Styler 物件並設定數字格式
    styler = df.style.format({
        'return_pct': '{:+.2f}%',
        'daily_vol': '{:.2f}%',
        'win_rate': '{:.0f}%'
    })

    # 1. 套用報酬率顏色與加粗
    styler = styler.map(color_return, subset=['return_pct'])

    # 2. 套用日均波動顏色 (取代原本的熱力圖)
    styler = styler.map(color_volatility, subset=['daily_vol'])

    return styler

def display_momentum_tables(region):
    momentum_df = get_short_term_momentum(region=region)
    
    if not momentum_df.empty:
        # 決定貨幣符號
        currency = "TWD " if region == "TW" else "USD "

        # 數據統計區間
        if 'start_date' in momentum_df.columns and 'latest_date' in momentum_df.columns:
            start_d = momentum_df['start_date'].iloc[0]
            end_d = momentum_df['latest_date'].iloc[0]
            st.caption(f"📅 數據統計區間：**{start_d}** 至 **{end_d}** (共 10 個交易日)")
        else:
            st.warning("⚠️ 數據欄位不完整，請檢查 db_connection.py 是否已存檔並重啟 App")
        
        # --- UI 優化：加入排序與篩選 ---
        col_filter, col_sort = st.columns(2)
        with col_filter:
            min_vol = st.number_input(f"最低10日均成交量 ({region})", value=100, step=100)
        with col_sort:
            sort_target = st.selectbox("排序依據", ["10日報酬率", "10日均量"], key=f"sort_{region}")

        # 過濾低流動性標的
        filtered_df = momentum_df[momentum_df['avg_volume'] >= min_vol]
        
        # 決定排序邏輯
        sort_col = 'return_pct' if sort_target == "10日報酬率" else 'avg_volume'

        # 加入排名欄位：噴發榜
        top_gainers = filtered_df.sort_values(sort_col, ascending=False).head(10).copy()
        if not top_gainers.empty:
            top_gainers.insert(0, "排名", range(1, len(top_gainers) + 1))
        
        # 加入排名欄位：超跌榜
        top_losers = filtered_df.sort_values('return_pct', ascending=True).head(10).copy()
        if not top_losers.empty:
            top_losers.insert(0, "排名", range(1, len(top_losers) + 1))

        # --- 表格定義更新 ---
        col_cfg = {
            "排名": st.column_config.TextColumn("No.", width=None),
            "etf_id": "ETF 代號",
            "start_price": st.column_config.NumberColumn(f"最初價({start_d})", format=f"%.2f {currency}", width="stretch"),
            "latest_price": st.column_config.NumberColumn(f"最新價({end_d})", format=f"%.2f {currency}", width="stretch"),
            "avg_volume": st.column_config.NumberColumn("10日均量", format="%,d", width="stretch"),
            "return_pct": st.column_config.NumberColumn("10日報酬", width="stretch"),
            "daily_vol": "日均波動",
            "win_rate": st.column_config.ProgressColumn("勝率", format="%.0f%%", min_value=0, max_value=100, width="stretch")
        }
        
        display_cols = ['排名', 'etf_id', 'start_price', 'latest_price', 'avg_volume', 'return_pct', 'daily_vol', 'win_rate']

        # 顯示噴發榜
        st.success(f"🚀 {region} 噴發榜 (依{sort_target}排序)")
        if not top_gainers.empty:
            st.dataframe(
                style_momentum_df(top_gainers[display_cols], region), 
                column_config=col_cfg, 
                hide_index=True, 
                width="stretch"
            )        

        st.write("")

        # 顯示超跌榜 (超跌榜通常還是看跌幅，所以固定依報酬率正序排序)
        st.error(f"📉 {region} 超跌榜 (依{sort_target}排序)")
        if not top_losers.empty:
            st.dataframe(
                style_momentum_df(top_losers[display_cols], region),
                column_config=col_cfg, 
                hide_index=True, 
                width="stretch"
            )    
        
    else:
        st.warning(f"⚠️ 目前無 {region} 的短期動能數據。")

if __name__ == "__main__":
    # 單獨測試此頁面
    st.set_page_config(page_title="短期動能測試", layout="wide")
    show_momentum_analysis()