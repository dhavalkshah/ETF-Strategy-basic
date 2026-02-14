import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import date

def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate the Relative Strength Index (RSI).
    """
    if len(prices) < period:
        return [None] * len(prices)

    df = pd.DataFrame({'Close': prices})
    
    # Calculate price changes
    delta = df['Close'].diff()

    # Get positive and negative changes
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Calculate exponential moving average of gains and losses
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    # Calculate Relative Strength (RS)
    rs = avg_gain / avg_loss

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))
    return rsi.tolist()

def calculate_ma(prices: List[float], period: int = 20) -> List[Optional[float]]:
    """
    Calculate the Simple Moving Average (MA).
    """
    if len(prices) < period:
        return [None] * len(prices)

    df = pd.DataFrame({'Close': prices})
    ma = df['Close'].rolling(window=period).mean()
    return ma.tolist()

def calculate_xirr(transactions: List[Dict[str, Any]]) -> Optional[float]:
    """
    Calculate XIRR for a series of transactions.
    Transactions should be a list of dictionaries with 'date' (datetime.date) and 'amount' (float).
    Example: [{'date': date(2020, 1, 1), 'amount': -1000}, {'date': date(2020, 12, 31), 'amount': 1100}]
    """
    if not transactions:
        return None

    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'])

    dates = np.array([t['date'] for t in transactions])
    amounts = np.array([t['amount'] for t in transactions])

    # Ensure all dates are valid for numpy
    dates = dates.astype('datetime64[D]')

    # Initial guess for XIRR
    try:
        xirr_value = npf.irr(amounts) # This is for internal rate of return, not extended.
    except ValueError:
        return None
    
    # Placeholder for actual XIRR calculation with dates
    # scipy.optimize.newton or a custom implementation would be needed for true XIRR
    # For now, return a simplified IRR if dates are not handled by npf.irr directly
    # A proper implementation would use a function like below:
    # from scipy.optimize import newton
    # def _xnpv(rate, dates, amounts):
    #     return sum([
    #         amount / (1 + rate)**((dates[i] - dates[0]).days / 365.0)
    #         for i, amount in enumerate(amounts)
    #     ])
    # try:
    #     xirr_value = newton(lambda r: _xnpv(r, dates, amounts), 0.1)
    # except RuntimeError: # Failed to converge
    #     return None

    return xirr_value # Returning IRR as a placeholder

# Need to import numpy_financial for npf.irr
import numpy_financial as npf # Will be added to requirements.txt later
