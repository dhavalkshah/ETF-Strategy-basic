import logging
from typing import List, Optional, Dict, Any
from datetime import date

import pandas as pd
import numpy as np
from scipy.optimize import newton

logger = logging.getLogger(__name__)


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate the Relative Strength Index (RSI).
    
    RSI measures momentum and identifies overbought (>70) or oversold (<30) conditions.
    
    Args:
        prices: List of closing prices
        period: RSI period (default 14)
        
    Returns:
        List of RSI values (None for initial periods where RSI cannot be calculated)
    """
    if not prices or len(prices) < period + 1:
        logger.warning(f"Insufficient data for RSI calculation. Need {period + 1} prices, got {len(prices)}")
        return [None] * len(prices)
    
    try:
        df = pd.DataFrame({'Close': prices})
        
        # Calculate price changes
        delta = df['Close'].diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calculate exponential moving average of gains and losses
        # Using ewm (exponential weighted moving) with Wilder's smoothing
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        
        # Calculate Relative Strength (RS)
        # Handle division by zero
        rs = avg_gain / avg_loss.replace(0, np.nan)
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        # Replace inf/nan with None for clarity
        rsi_list = rsi.tolist()
        return [None if pd.isna(val) or np.isinf(val) else val for val in rsi_list]
        
    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        return [None] * len(prices)


def calculate_ma(prices: List[float], period: int = 20) -> List[Optional[float]]:
    """
    Calculate the Simple Moving Average (SMA).
    
    Args:
        prices: List of closing prices
        period: MA period (default 20)
        
    Returns:
        List of MA values (None for initial periods)
    """
    if not prices or len(prices) < period:
        logger.warning(f"Insufficient data for MA calculation. Need {period} prices, got {len(prices)}")
        return [None] * len(prices)
    
    try:
        df = pd.DataFrame({'Close': prices})
        ma = df['Close'].rolling(window=period).mean()
        
        ma_list = ma.tolist()
        return [None if pd.isna(val) else val for val in ma_list]
        
    except Exception as e:
        logger.error(f"Error calculating MA: {e}")
        return [None] * len(prices)


def calculate_ema(prices: List[float], period: int = 20) -> List[Optional[float]]:
    """
    Calculate the Exponential Moving Average (EMA).
    
    EMA gives more weight to recent prices compared to SMA.
    
    Args:
        prices: List of closing prices
        period: EMA period (default 20)
        
    Returns:
        List of EMA values
    """
    if not prices or len(prices) < period:
        logger.warning(f"Insufficient data for EMA calculation. Need {period} prices, got {len(prices)}")
        return [None] * len(prices)
    
    try:
        df = pd.DataFrame({'Close': prices})
        ema = df['Close'].ewm(span=period, adjust=False).mean()
        
        ema_list = ema.tolist()
        return [None if pd.isna(val) else val for val in ema_list]
        
    except Exception as e:
        logger.error(f"Error calculating EMA: {e}")
        return [None] * len(prices)


def calculate_xirr(transactions: List[Dict[str, Any]]) -> Optional[float]:
    """
    Calculate XIRR (Extended Internal Rate of Return) for irregular cash flows.
    
    XIRR is the rate of return that makes the Net Present Value (NPV) of all 
    cash flows equal to zero, accounting for the timing of each transaction.
    
    Args:
        transactions: List of dicts with 'date' (datetime.date) and 'amount' (float)
                     Negative amounts = investments (outflows)
                     Positive amounts = returns (inflows)
                     Example: [
                         {'date': date(2020, 1, 1), 'amount': -1000},
                         {'date': date(2020, 6, 1), 'amount': -500},
                         {'date': date(2020, 12, 31), 'amount': 1600}
                     ]
    
    Returns:
        XIRR as a decimal (e.g., 0.15 for 15% annual return)
        None if calculation fails or data is invalid
    """
    if not transactions or len(transactions) < 2:
        logger.warning("XIRR requires at least 2 transactions")
        return None
    
    try:
        # Sort transactions by date
        sorted_transactions = sorted(transactions, key=lambda x: x['date'])
        
        dates = [t['date'] for t in sorted_transactions]
        amounts = [t['amount'] for t in sorted_transactions]
        
        # Validate data
        if not all(isinstance(d, date) for d in dates):
            logger.error("All dates must be datetime.date objects")
            return None
        
        if not all(isinstance(a, (int, float)) for a in amounts):
            logger.error("All amounts must be numeric")
            return None
        
        # Check if all amounts are same sign (no actual transactions)
        if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
            logger.warning("XIRR requires both positive and negative cash flows")
            return None
        
        # Calculate XNPV for a given rate
        def xnpv(rate: float) -> float:
            """Calculate Net Present Value for irregular cash flows."""
            if rate <= -1.0:
                return float('inf')
            
            t0 = dates[0]
            npv = sum(
                amount / (1.0 + rate) ** ((d - t0).days / 365.0)
                for d, amount in zip(dates, amounts)
            )
            return npv
        
        # Calculate derivative for faster convergence
        def xnpv_derivative(rate: float) -> float:
            """Calculate derivative of XNPV for Newton's method."""
            if rate <= -1.0:
                return 0
            
            t0 = dates[0]
            derivative = sum(
                -amount * ((d - t0).days / 365.0) / (1.0 + rate) ** (((d - t0).days / 365.0) + 1)
                for d, amount in zip(dates, amounts)
            )
            return derivative
        
        # Solve for XIRR using Newton's method
        # Try with derivative first (faster)
        try:
            xirr_value = newton(func=xnpv, x0=0.1, fprime=xnpv_derivative, maxiter=100)
        except (RuntimeError, ValueError):
            # If derivative method fails, try without derivative
            try:
                xirr_value = newton(func=xnpv, x0=0.1, maxiter=100)
            except (RuntimeError, ValueError):
                # Try different initial guesses
                for guess in [0.01, -0.05, 0.5, -0.5]:
                    try:
                        xirr_value = newton(func=xnpv, x0=guess, maxiter=100)
                        break
                    except (RuntimeError, ValueError):
                        continue
                else:
                    logger.warning("XIRR calculation failed to converge with all initial guesses")
                    return None
        
        # Validate result is reasonable (between -100% and 10000% annual return)
        if xirr_value < -0.99 or xirr_value > 100:
            logger.warning(f"XIRR result seems unreasonable: {xirr_value * 100:.2f}%")
            return None
        
        return xirr_value
        
    except Exception as e:
        logger.error(f"Error calculating XIRR: {e}")
        return None


def calculate_cagr(
    start_value: float,
    end_value: float,
    start_date: date,
    end_date: date
) -> Optional[float]:
    """
    Calculate Compound Annual Growth Rate (CAGR).
    
    CAGR = (End Value / Start Value) ^ (1 / Years) - 1
    
    Args:
        start_value: Initial portfolio value
        end_value: Final portfolio value
        start_date: Start date
        end_date: End date
        
    Returns:
        CAGR as a decimal (e.g., 0.12 for 12% annual growth)
        None if calculation fails
    """
    try:
        if start_value <= 0:
            logger.warning("Start value must be positive for CAGR calculation")
            return None
        
        if end_date <= start_date:
            logger.warning("End date must be after start date for CAGR calculation")
            return None
        
        # Calculate years (using actual days)
        days = (end_date - start_date).days
        years = days / 365.25  # Account for leap years
        
        if years <= 0:
            logger.warning("Time period too short for CAGR calculation")
            return None
        
        # CAGR formula
        cagr = (end_value / start_value) ** (1 / years) - 1
        
        return cagr
        
    except Exception as e:
        logger.error(f"Error calculating CAGR: {e}")
        return None


def calculate_max_drawdown(equity_curve: List[float]) -> Optional[float]:
    """
    Calculate maximum drawdown from equity curve.
    
    Drawdown is the peak-to-trough decline during a specific period.
    
    Args:
        equity_curve: List of portfolio values over time
        
    Returns:
        Maximum drawdown as a negative decimal (e.g., -0.15 for 15% drawdown)
        None if calculation fails
    """
    try:
        if not equity_curve or len(equity_curve) < 2:
            return None
        
        equity_array = np.array(equity_curve)
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(equity_array)
        
        # Calculate drawdown at each point
        drawdown = (equity_array - running_max) / running_max
        
        # Maximum drawdown is the minimum value (most negative)
        max_dd = np.min(drawdown)
        
        return float(max_dd) if not np.isnan(max_dd) else None
        
    except Exception as e:
        logger.error(f"Error calculating max drawdown: {e}")
        return None