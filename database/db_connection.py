import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict

from sqlalchemy import text

from database import logger, engine


# ================================
# 資料讀取函式 (用於 Streamlit App)
# ================================

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

