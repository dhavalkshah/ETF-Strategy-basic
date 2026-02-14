from datetime import date
from typing import Optional, Dict, Any

from app.strategy.calculations import calculate_rsi
from app.strategy.models import AdvisorRecommendation
from app.db.models import HistoricalPrice

def get_advisor_recommendation(
    current_holdings: Dict[str, float], # {instrument_symbol: units}
    cash_balance: float,
    historical_prices: List[HistoricalPrice], # Full historical data for RSI calculation
    sip_amount: float,
    dip_multiplier: float = 1.0
) -> AdvisorRecommendation:
    """
    Generates a daily investment recommendation for a given instrument.
    """
    if not historical_prices:
        return AdvisorRecommendation(
            recommended_amount=0.0,
            reason="No historical data available for the instrument.",
            portfolio_state_snapshot={
                "current_holdings": current_holdings,
                "cash_balance": cash_balance
            }
        )
    
    # Ensure historical prices are sorted by date
    historical_prices.sort(key=lambda hp: hp.date)

    # Get the last available historical data point (yesterday's close)
    last_day_historical_data = historical_prices[-1]
    current_close = last_day_historical_data.close

    # Calculate RSI using the provided historical prices
    closes = [hp.close for hp in historical_prices]
    rsi_values = calculate_rsi(closes)
    
    # Use the last valid RSI value
    current_rsi = None
    for rsi_val in reversed(rsi_values):
        if rsi_val is not None:
            current_rsi = rsi_val
            break
    
    if current_rsi is None:
        return AdvisorRecommendation(
            recommended_amount=0.0,
            reason="Could not calculate RSI from available historical data.",
            portfolio_state_snapshot={
                "current_holdings": current_holdings,
                "cash_balance": cash_balance,
                "last_close_price": current_close
            }
        )

    recommended_amount = 0.0
    reason = "No specific recommendation based on current market conditions."

    if current_rsi < 30: # Buy condition: RSI < 30
        buy_amount = sip_amount * dip_multiplier
        recommended_amount = buy_amount
        reason = f"RSI is low ({current_rsi:.2f}), indicating a potential buying opportunity. Recommend a dip buy."
    
    portfolio_snapshot = {
        "current_holdings": current_holdings,
        "cash_balance": cash_balance,
        "last_close_price": current_close,
        "current_rsi": current_rsi
    }

    return AdvisorRecommendation(
        recommended_amount=recommended_amount,
        reason=reason,
        portfolio_state_snapshot=portfolio_snapshot
    )