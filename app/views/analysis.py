import streamlit as st
from database.db_connection import get_short_term_momentum

def show_momentum_analysis():
    st.markdown("# **🔥 ETF 短期動能快訊 (近兩週)**")
    
    # 建立台股與美股的 Tab
    tab_tw, tab_us = st.tabs(["🇹🇼 台股 ETF", "🇺🇸 美股 ETF"])
    
    # --- 台股分頁 ---
    with tab_tw:
        display_momentum_tables(region="TW")
        
    # --- 美股分頁 ---
    with tab_us:
        display_momentum_tables(region="US")

def display_momentum_tables(region):
    """
    封裝顯示邏輯，根據傳入的 region 顯示對應的漲跌榜
    """
    momentum_df = get_short_term_momentum(region=region)
    
    if not momentum_df.empty:
        # 安全讀取：確保欄位存在
        if 'start_date' in momentum_df.columns and 'latest_date' in momentum_df.columns:
            start_d = momentum_df['start_date'].iloc[0]
            end_d = momentum_df['latest_date'].iloc[0]
            st.caption(f"📅 數據統計區間：**{start_d}** 至 **{end_d}** (共 10 個交易日)")
        else:
            st.warning("⚠️ 數據欄位不完整，請檢查 db_connection.py 是否已存檔並重啟 App")
        
        # 定義統一的表格配置，減少重複代碼
        col_cfg = {
            "etf_id": "ETF 代號",
            "latest_price": st.column_config.NumberColumn("最新價", format="%.2f"),
            "return_pct": st.column_config.NumberColumn("兩週漲幅", format="%.2f%%"),
            "ann_return": st.column_config.NumberColumn("年化報酬(預估)", format="%.1f%%"),
            "ann_volatility": st.column_config.NumberColumn("年化波動度", format="%.1f%%")
        }
        # 需要顯示的欄位
        display_cols = ['etf_id', 'latest_price', 'return_pct', 'ann_return', 'ann_volatility']

        # 1. 顯示噴發榜 (直接佔滿寬度)
        st.success(f"🚀 {region} 漲幅前五名 (噴發榜)")
        top_gainers = momentum_df.sort_values('return_pct', ascending=False).head(5)
        st.dataframe(top_gainers[display_cols], column_config=col_cfg, hide_index=True, width='stretch')
        
        # 加入一個小間距
        st.write("") 

        # 2. 顯示超跌榜 (直接佔滿寬度)
        st.error(f"📉 {region} 跌幅前五名 (超跌榜)")
        top_losers = momentum_df.sort_values('return_pct', ascending=True).head(5)
        st.dataframe(top_losers[display_cols], column_config=col_cfg, hide_index=True, width='stretch')
        
    else:
        st.warning(f"⚠️ 目前無 {region} 的短期動能數據，請確認資料庫已正確同步。")

# 執行主函式
show_momentum_analysis()