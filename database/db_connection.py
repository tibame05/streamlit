import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict
import numpy as np

from sqlalchemy import text

from database import logger, engine
from database import SessionLocal

# ================================
# 資料讀取函式 (用於 Streamlit App)
# ================================


def get_etf_overview(region=None, min_return_1y=None, max_expense_ratio=None, 
                     etf_ids=None, sort_by='ETF代號', ascending=True, 
                     time_period='不限', exclude_outliers=False):
    """
    獲取 ETF 概覽資訊 (已修正 SQL 語法)
    """
    
    # 1. 定義時間區間對應的 SQL 檢查欄位
    period_map = {
        "不限": {"check": "bt.cagr_1y", "vol": "bt.volatility_1y"},
        "1年":  {"check": "bt.cagr_1y", "vol": "bt.volatility_1y"},
        "3年":  {"check": "bt.cagr_3y", "vol": "bt.volatility_3y"},
        "10年": {"check": "bt.cagr_10y", "vol": "bt.volatility_10y"}
    }

    # 取得當前區間要使用的欄位名稱，預設用 1y
    target = period_map.get(time_period, period_map["不限"])
    check_col = target["check"]
    vol_col = target["vol"]

    query = f"""
    SELECT 
        e.etf_id AS 'ETF代號',
        e.etf_name AS 'ETF名稱',
        e.expense_ratio AS '管理費(%)',
        e.inception_date AS '成立日',

        -- 成交量統計
        COALESCE(ROUND(vol.volume_1y, 0), 0) AS '1年成交量總和',
        COALESCE(ROUND(vol.volume_3y, 0), 0) AS '3年成交量總和',
        COALESCE(ROUND(vol.volume_10y, 0), 0) AS '10年成交量總和',

        -- 年化報酬率
        ROUND(bt.cagr_1y * 100, 2) AS '1年報酬率(%)',
        ROUND(bt.cagr_3y * 100, 2) AS '3年報酬率(%)',
        ROUND(bt.cagr_10y * 100, 2) AS '10年報酬率(%)',

        -- 年化波動度
        ROUND(bt.volatility_1y * 100, 2) AS '1年波動度(%)',
        ROUND(bt.volatility_3y * 100, 2) AS '3年波動度(%)',
        ROUND(bt.volatility_10y * 100, 2) AS '10年波動度(%)'
    
    FROM etfs e
    LEFT JOIN (
        SELECT 
            etf_id,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR) THEN volume END) AS volume_1y,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR) THEN volume END) AS volume_3y,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 10 YEAR) THEN volume END) AS volume_10y
        FROM etf_daily_prices
        GROUP BY etf_id
    ) vol ON e.etf_id = vol.etf_id
    INNER JOIN (
        SELECT 
            etf_id,
            MAX(CASE WHEN label = '1y' THEN cagr END) AS cagr_1y,
            MAX(CASE WHEN label = '3y' THEN cagr END) AS cagr_3y,
            MAX(CASE WHEN label = '10y' THEN cagr END) AS cagr_10y,
            MAX(CASE WHEN label = '1y' THEN volatility END) AS volatility_1y,
            MAX(CASE WHEN label = '3y' THEN volatility END) AS volatility_3y,
            MAX(CASE WHEN label = '10y' THEN volatility END) AS volatility_10y
        FROM etf_backtests
        GROUP BY etf_id
    ) bt ON e.etf_id = bt.etf_id

    WHERE 1=1
      -- 確保當前篩選的時間段有數據
      AND {check_col} IS NOT NULL
      
      -- 排除異常值
      AND {vol_col} > 0
    """
    
    params = {}

    if exclude_outliers:
        query += f" AND {vol_col} <= 0.30" # 波動度小於等於 30%

    if region:
        query += " AND e.region = :region"
        params['region'] = region
    
    if etf_ids:
        placeholders = ','.join([f':etf_id_{i}' for i in range(len(etf_ids))])
        query += f" AND e.etf_id IN ({placeholders})"
        for i, etf_id in enumerate(etf_ids):
            params[f'etf_id_{i}'] = etf_id
    
    # 最低報酬率篩選
    if min_return_1y is not None:
        query += " AND bt.cagr_1y >= :min_return"
        params['min_return'] = min_return_1y
    
    # 最高管理費篩選
    if max_expense_ratio is not None:
        query += " AND e.expense_ratio <= :max_expense"
        params['max_expense'] = max_expense_ratio
    
    with SessionLocal() as session:
        result = session.execute(text(query), params)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    
    # 排序
    if not df.empty and sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=ascending)
        df = df.reset_index(drop=True)
    
    return df


def get_etf_list_by_region(region: str) -> list:
    """
    取得地區 ETF 列表：
    1. 必須是 ACTIVE 狀態
    2. 必須在 etf_backtests 資料表中至少有一筆資料 (確保至少滿一年)
    """
    query = text("""
        SELECT e.etf_id, e.etf_name 
        FROM etfs e
        WHERE e.region = :region 
          AND e.status = 'ACTIVE'
          AND EXISTS (
              SELECT 1 FROM etf_backtests b 
              WHERE b.etf_id = e.etf_id
          )
        ORDER BY e.etf_id
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"region": region})
            return [f"{row[0]} {row[1]}" for row in result]
    except Exception as e:
        logger.error(f"Failed to get ETF list for region {region}: {e}")
        return []


def get_etf_kline_data(etf_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    讀取指定 ETF 在日期區間內的 OHLCV 資料，用於繪製 K 線圖。
    
    parameters:
        etf_id (str): ETF 代碼
        start_date (str): 起始日期 (YYYY-MM-DD)
        end_date (str): 結束日期 (YYYY-MM-DD)
    
    returns:
        pd.DataFrame: 包含 trade_date, open, high, low, close, volume
    """
    # 根據需求選取 OHLCV 欄位
    query = text("""
        SELECT 
            trade_date,
            open,
            high,
            low,
            close,
            volume
        FROM etf_daily_prices
        WHERE etf_id = :etf_id
          AND trade_date BETWEEN :start_date AND :end_date
        ORDER BY trade_date
    """)
    
    try:
        df = pd.read_sql(
            query, 
            engine, 
            params={
                "etf_id": etf_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            
            # 確保數值型態正確 (避免 Decimal 或字串導致繪圖錯誤)
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        logger.info(f"Loaded {len(df)} K-line records for {etf_id}")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load K-line data for {etf_id}: {e}", exc_info=True)
        return pd.DataFrame()


def get_etf_backtest_metrics(etf_id: str, label: str) -> Dict:
    """
    讀取指定 ETF 在特定年限的回測績效。
    
    parameters:
        etf_id (str): ETF 代碼
        label (str): 回測期間 ('1y', '3y', '10y')
    
    returns:
        dict: 回測績效數據，包含 cagr, sharpe_ratio, total_return 等。
    """
    query = text("""
        SELECT 
            start_date,
            end_date,
            cagr,
            sharpe_ratio,
            max_drawdown,
            total_return,
            volatility
        FROM etf_backtests
        WHERE etf_id = :etf_id AND label = :label
    """)
    
    try:
        df = pd.read_sql(
            query, 
            engine, 
            params={"etf_id": etf_id, "label": label}
        )
        
        if not df.empty:
            # 將數值欄位轉換為浮點數，方便後續計算
            metrics = df.iloc[0].to_dict()
            for key in ['cagr', 'sharpe_ratio', 'max_drawdown', 'total_return', 'volatility']:
                if key in metrics and metrics[key] is not None:
                    metrics[key] = float(metrics[key])
            
            logger.info(f"Loaded backtest metrics for {etf_id} ({label})")
            return metrics
        else:
            logger.warning(f"No backtest metrics found for {etf_id} ({label})")
            return {}
            
    except Exception as e:
        logger.error(f"Failed to load backtest metrics for {etf_id}: {e}", exc_info=True)
        return {}


def get_etf_prices(etf_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    讀取指定 ETF 在日期區間內的價格資料。
    
    parameters:
        etf_id (str): ETF 代碼
        start_date (str): 起始日期 (YYYY-MM-DD)
        end_date (str): 結束日期 (YYYY-MM-DD)
    
    returns:
        pd.DataFrame: 價格資料，包含 trade_date, adj_close
    """
    query = text("""
        SELECT trade_date, adj_close
        FROM etf_daily_prices
        WHERE etf_id = :etf_id
          AND trade_date BETWEEN :start_date AND :end_date
        ORDER BY trade_date
    """)
    
    try:
        df = pd.read_sql(
            query, 
            engine, 
            params={
                "etf_id": etf_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        logger.info(f"Loaded {len(df)} price records for {etf_id}")
        return df
    except Exception as e:
        logger.error(f"Failed to load prices for {etf_id}: {e}", exc_info=True)
        return pd.DataFrame()


def get_short_term_momentum(region="TW"):
    """
    計算資料庫內最新兩週 (10個交易日) 的 ETF 漲跌動能指標
    指標包含：期間報酬率、日均波動、勝率
    """
    # 撰寫 SQL 抓取近 15 天的價格 (多抓幾天以確保有 10 個交易日)
    query = text("""
        SELECT etf_id, trade_date, adj_close, volume
        FROM (
            SELECT etf_id, trade_date, adj_close, volume,
                   ROW_NUMBER() OVER (PARTITION BY etf_id ORDER BY trade_date DESC) as rn
            FROM etf_daily_prices
            WHERE etf_id IN (SELECT etf_id FROM etfs WHERE region = :region)
        ) t
        WHERE rn <= 15  -- 每檔 ETF 只抓最新的 15 筆，確保足夠計算 10 天變動
    """)

    try:
        # 使用 engine 連線讀取
        df = pd.read_sql(query, engine, params={"region": region})

        if df.empty:
            return pd.DataFrame()

        # --- 模擬計算邏輯 ---
        results = []
        
        # 對每一檔 ETF 進行分組計算
        for etf_id, group in df.groupby('etf_id'):
            # 確保排序正確 (由舊到新)
            group = group.sort_values('trade_date', ascending=True).reset_index(drop=True)
            
            # 確保有足夠的資料點計算變動 (11點才能產生10個變動區間)
            if len(group) < 11: continue 
            target_group = group.tail(11).reset_index(drop=True)
            
            # 取得用於計算的價格序列
            prices = target_group['adj_close'].astype(float)
            daily_returns = prices.pct_change().dropna() 
            
            # 取出 14 日前(第1筆)與最新(最後1筆)價格
            start_price = float(prices.iloc[0])
            latest_price = float(prices.iloc[-1])
            
            # --- 指標計算 ---
            # 1. 期間報酬率 (Total 2-Week Return)
            return_pct = (latest_price - start_price) / start_price
            
            # 2. 日均波動 (Daily Volatility)
            daily_vol = daily_returns.abs().mean()
            
            # 3. 勝率 (Winning Days Rate)
            win_days = (daily_returns > 0).sum()
            win_rate = win_days / len(daily_returns)
            
            # 修正重點 2: 計算 10 日平均成交量 (取出最後 10 筆交易日)
            avg_vol = group['volume'].astype(float).tail(10).mean()
            
            results.append({
                'etf_id': etf_id,
                'start_date': group.iloc[0]['trade_date'],
                'start_price': start_price,          # 對應 analysis.py
                'latest_date': group.iloc[-1]['trade_date'],
                'latest_price': latest_price,        # 對應 analysis.py
                'avg_volume': avg_vol,               # 對應 analysis.py
                'return_pct': return_pct * 100,      
                'daily_vol': daily_vol * 100,        
                'win_rate': win_rate * 100
            })            
        return pd.DataFrame(results)    
    except Exception as e:
        logger.error(f"短期動能計算失敗: {e}")
        return pd.DataFrame()
    

# ================================
# 可能沒用到的資料讀取函式 (保留以備未來擴充)
# ================================

def get_etf_summary() -> pd.DataFrame:
    """
    讀取 ETF 摘要資料，用於總覽頁面。
    從 etfs, etf_backtests, etf_daily_prices 關聯查詢。
    
    returns:
        pd.DataFrame: ETF 摘要資料，包含 etf_id, name, region, expense_ratio, 
                     inception_date, volume, annual_return_3y, volatility_3y
    """

    query = """
        SELECT 
            e.etf_id,
            e.etf_name AS name,
            e.region,
            e.expense_ratio,
            e.inception_date,
            
            -- 使用近一年成交量總和作為 volume 代表
            COALESCE(vol.volume_1y, 0) AS volume,
            
            -- 3年年化報酬率 (轉換為百分比)
            ROUND(bt.cagr * 100, 2) AS annual_return_3y,
            
            -- 3年波動度 (轉換為百分比)
            ROUND(bt.volatility * 100, 2) AS volatility_3y
            
        FROM etfs e
        
        -- 關聯近一年成交量
        LEFT JOIN (
            SELECT 
                etf_id, 
                SUM(volume) as volume_1y 
            FROM etf_daily_prices 
            WHERE trade_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR) 
            GROUP BY etf_id
        ) vol ON e.etf_id = vol.etf_id
        
        -- 關聯 3 年回測數據
        LEFT JOIN etf_backtests bt ON e.etf_id = bt.etf_id AND bt.label = '3y'
        
        WHERE e.status = 'ACTIVE'
        ORDER BY volume DESC
    """
    try:
        df = pd.read_sql(query, engine)
        logger.info(f"Loaded {len(df)} ETF summary records")
        return df
    except Exception as e:
        logger.error(f"Failed to load ETF summary: {e}", exc_info=True)
        return pd.DataFrame()


def get_active_etfs() -> pd.DataFrame:
    """
    讀取所有活躍的 ETF 清單。
    
    returns:
        pd.DataFrame: ETF 清單，包含 etf_id, name, region
    """
    query = """
        SELECT etf_id, name, region 
        FROM etfs 
        WHERE status = 'ACTIVE' 
        ORDER BY name
    """
    try:
        df = pd.read_sql(query, engine)
        logger.info(f"Loaded {len(df)} active ETF records")
        return df
    except Exception as e:
        logger.error(f"Failed to load active ETFs: {e}", exc_info=True)
        return pd.DataFrame()


def get_etf_table_with_metrics() -> pd.DataFrame:
    """
    讀取完整的 ETF 表格，包含回測績效指標。
    用於「ETF 總表」視覺化。
    
    returns:
        pd.DataFrame: 包含 ETF 基本資料 + 回測績效（1y, 3y, 10y）
            - etf_id, etf_name, region, expense_ratio, inception_date
            - avg_dividend_1y (近一年平均配息)
            - volume_sum_1y, volume_sum_3y, volume_sum_10y (成交量總和)
            - cagr_1y, cagr_3y, cagr_10y (年化報酬率)
            - volatility_1y, volatility_3y, volatility_10y (波動度)
    """
    query = """
        SELECT 
            e.etf_id,
            e.etf_name,
            e.region,
            e.expense_ratio,
            e.inception_date,
            
            -- 近一年平均配息
            COALESCE(
                (SELECT AVG(dividend_per_unit) 
                 FROM etf_dividends d 
                 WHERE d.etf_id = e.etf_id 
                   AND d.ex_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)),
                0
            ) AS avg_dividend_1y,
            
            -- 回測績效（1年）
            b1.cagr AS cagr_1y,
            b1.volatility AS volatility_1y,
            b1.max_drawdown AS max_drawdown_1y,
            b1.sharpe_ratio AS sharpe_ratio_1y,
            
            -- 回測績效（3年）
            b3.cagr AS cagr_3y,
            b3.volatility AS volatility_3y,
            b3.max_drawdown AS max_drawdown_3y,
            b3.sharpe_ratio AS sharpe_ratio_3y,
            
            -- 回測績效（10年）
            b10.cagr AS cagr_10y,
            b10.volatility AS volatility_10y,
            b10.max_drawdown AS max_drawdown_10y,
            b10.sharpe_ratio AS sharpe_ratio_10y
            
        FROM etfs e
        LEFT JOIN etf_backtests b1 ON e.etf_id = b1.etf_id AND b1.label = '1y'
        LEFT JOIN etf_backtests b3 ON e.etf_id = b3.etf_id AND b3.label = '3y'
        LEFT JOIN etf_backtests b10 ON e.etf_id = b10.etf_id AND b10.label = '10y'
        WHERE e.status = 'ACTIVE'
        ORDER BY e.etf_id
    """
    
    try:
        df = pd.read_sql(query, engine)
        logger.info(f"Loaded {len(df)} ETF records with metrics")
        return df
    except Exception as e:
        logger.error(f"Failed to load ETF table with metrics: {e}", exc_info=True)
        return pd.DataFrame()


def get_etf_backtest_data(period: str = '3y') -> pd.DataFrame:
    """
    讀取指定期間的回測數據，用於風險–報酬散點圖。
    
    parameters:
        period (str): 回測期間 ('1y', '3y', '10y')
    
    returns:
        pd.DataFrame: 包含 etf_id, etf_name, region, cagr, volatility, volume_sum
    """
    query = text("""
        SELECT 
            e.etf_id,
            e.etf_name,
            e.region,
            b.cagr,
            b.volatility,
            b.max_drawdown,
            b.sharpe_ratio,
            b.total_return,
            -- 計算該期間的平均成交量
            (SELECT AVG(volume) 
             FROM etf_daily_prices p 
             WHERE p.etf_id = e.etf_id 
               AND p.trade_date >= b.start_date 
               AND p.trade_date <= b.end_date
            ) AS avg_volume
        FROM etfs e
        INNER JOIN etf_backtests b ON e.etf_id = b.etf_id
        WHERE e.status = 'ACTIVE'
          AND b.label = :period
    """)
    
    try:
        df = pd.read_sql(query, engine, params={"period": period})
        logger.info(f"Loaded {len(df)} backtest records for period {period}")
        return df
    except Exception as e:
        logger.error(f"Failed to load backtest data for {period}: {e}", exc_info=True)
        return pd.DataFrame()
    

def get_etf_info(etf_id: str) -> Dict:
    """
    讀取單一 ETF 的基本資訊。
    
    parameters:
        etf_id (str): ETF 代碼
    
    returns:
        dict: ETF 基本資訊
    """
    query = text("""
        SELECT 
            etf_id,
            etf_name,
            region,
            currency,
            expense_ratio,
            inception_date,
            status
        FROM etfs
        WHERE etf_id = :etf_id
    """)
    
    try:
        df = pd.read_sql(query, engine, params={"etf_id": etf_id})
        if not df.empty:
            logger.info(f"Loaded info for {etf_id}")
            return df.iloc[0].to_dict()
        else:
            logger.warning(f"No info found for {etf_id}")
            return {}
    except Exception as e:
        logger.error(f"Failed to load info for {etf_id}: {e}", exc_info=True)
        return {}


def get_etf_backtest_by_id(etf_id: str, period: str) -> Dict:
    """
    讀取指定 ETF 的回測績效。
    
    parameters:
        etf_id (str): ETF 代碼
        period (str): 回測期間 ('1y', '3y', '10y')
    
    returns:
        dict: 回測績效數據
    """
    query = text("""
        SELECT 
            start_date,
            end_date,
            cagr,
            sharpe_ratio,
            max_drawdown,
            total_return,
            volatility
        FROM etf_backtests
        WHERE etf_id = :etf_id AND label = :period
    """)
    
    try:
        df = pd.read_sql(query, engine, params={"etf_id": etf_id, "period": period})
        if not df.empty:
            logger.info(f"Loaded backtest for {etf_id} ({period})")
            return df.iloc[0].to_dict()
        else:
            logger.warning(f"No backtest found for {etf_id} ({period})")
            return {}
    except Exception as e:
        logger.error(f"Failed to load backtest for {etf_id} ({period}): {e}", exc_info=True)
        return {}