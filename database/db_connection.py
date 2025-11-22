import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict

from sqlalchemy import text

from database import logger, engine
from database import SessionLocal

# ================================
# 資料讀取函式 (用於 Streamlit App)
# ================================

def get_etf_overview(region=None, min_return_1y=None, max_expense_ratio=None, 
                     etf_ids=None, sort_by='ETF代號', ascending=True):
    """
    獲取 ETF 概覽資訊 (直接從資料庫查詢)
    
    Args:
        region (str, optional): 地區篩選 ('TW' 或 'US')
        min_return_1y (float, optional): 最低1年報酬率 (例如: 0.1 代表 10%)
        max_expense_ratio (float, optional): 最高管理費 (例如: 0.5 代表 0.5%)
        etf_ids (list, optional): 指定 ETF 代號列表
        sort_by (str): 排序欄位
        ascending (bool): 是否升序排序
    
    Returns:
        DataFrame: ETF 概覽資料
    """
    query = """
    SELECT 
        e.etf_id AS 'ETF代號',
        e.etf_name AS 'ETF名稱',
        e.expense_ratio AS '管理費(%)',
        e.inception_date AS '成立日',
        
        -- 成交量總和 (1/3/10年)
        COALESCE(ROUND(vol.volume_1y, 0), 0) AS '1年成交量總和',
        COALESCE(ROUND(vol.volume_3y, 0), 0) AS '3年成交量總和',
        COALESCE(ROUND(vol.volume_10y, 0), 0) AS '10年成交量總和',
        
        -- 年化報酬率 (1/3/10年)
        ROUND(COALESCE(bt.cagr_1y, 0) * 100, 2) AS '1年報酬率(%)',
        ROUND(COALESCE(bt.cagr_3y, 0) * 100, 2) AS '3年報酬率(%)',
        ROUND(COALESCE(bt.cagr_10y, 0) * 100, 2) AS '10年報酬率(%)',
        
        -- 年化波動度 (1/3/10年)
        ROUND(COALESCE(bt.volatility_1y, 0) * 100, 2) AS '1年波動度(%)',
        ROUND(COALESCE(bt.volatility_3y, 0) * 100, 2) AS '3年波動度(%)',
        ROUND(COALESCE(bt.volatility_10y, 0) * 100, 2) AS '10年波動度(%)'
        
    FROM etfs e
    
    -- 成交量統計
    LEFT JOIN (
        SELECT 
            etf_id,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR) THEN volume END) AS volume_1y,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 3 YEAR) THEN volume END) AS volume_3y,
            SUM(CASE WHEN trade_date >= DATE_SUB(CURDATE(), INTERVAL 10 YEAR) THEN volume END) AS volume_10y
        FROM etf_daily_prices
        GROUP BY etf_id
    ) vol ON e.etf_id = vol.etf_id
    
    -- 回測資料 (報酬率 + 波動度)
    LEFT JOIN (
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
    """
    
    params = {}
    
    # 地區篩選
    if region:
        query += " AND e.region = :region"
        params['region'] = region
    
    # ETF 代號篩選
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
    根據地區取得 ETF 代號列表 (用於下拉選單)
    """
    query = text("SELECT etf_id, etf_name FROM etfs WHERE region = :region AND status = 'ACTIVE' ORDER BY etf_id")
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

# =================================================
# 以下是原本的
# =================================================

def get_etf_summary() -> pd.DataFrame:
    """
    讀取 ETF 摘要資料，用於總覽頁面。
    
    returns:
        pd.DataFrame: ETF 摘要資料，包含 etf_id, name, region, expense_ratio, 
                     inception_date, volume, annual_return_3y, volatility_3y
    """
    query = """
        SELECT etf_id, name, region, expense_ratio, 
               inception_date, volume, 
               annual_return_3y, volatility_3y
        FROM etf_summary
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


def get_etf_ohlcv(etf_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    讀取 K 棒資料（OHLCV）。
    
    parameters:
        etf_id (str): ETF 代碼
        start_date (str): 起始日期 (YYYY-MM-DD)
        end_date (str): 結束日期 (YYYY-MM-DD)
    
    returns:
        pd.DataFrame: 包含 trade_date, open, high, low, close, adj_close, volume
    """
    query = text("""
        SELECT 
            trade_date,
            open,
            high,
            low,
            close,
            adj_close,
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
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        logger.info(f"Loaded {len(df)} OHLCV records for {etf_id}")
        return df
    except Exception as e:
        logger.error(f"Failed to load OHLCV for {etf_id}: {e}", exc_info=True)
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