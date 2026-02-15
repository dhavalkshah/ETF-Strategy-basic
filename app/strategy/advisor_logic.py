import logging
from typing import List, Dict, Optional

from app.strategy.calculations import calculate_rsi, calculate_ma
from app.strategy.models import AdvisorRecommendation
from app.db.models import HistoricalPrice

logger = logging.getLogger(__name__)


# RSI thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_STRONG_OVERSOLD = 25
RSI_EXTREME_OVERSOLD = 20


def get_advisor_recommendation(
    current_holdings: Dict[str, float],
    cash_balance: float,
    historical_prices: List[HistoricalPrice],
    sip_amount: float,
    dip_multiplier: float = 1.0
) -> AdvisorRecommendation:
    """
    Generates daily investment recommendation based on RSI analysis.
    
    Recommendation Logic:
    - RSI < 30: Oversold - recommend dip buy at dip_multiplier * SIP
    - RSI 30-70: Normal - recommend regular SIP
    - RSI > 70: Overbought - recommend holding (no investment)
    
    Enhanced logic for stronger signals:
    - RSI < 25: Strong oversold - recommend 1.5x dip buy
    - RSI < 20: Extreme oversold - recommend 2x dip buy
    
    Args:
        current_holdings: Dictionary of current holdings {symbol: units}
        cash_balance: Available cash balance
        historical_prices: Historical price data for RSI calculation
        sip_amount: Regular SIP amount
        dip_multiplier: Multiplier for dip buying (default 1.0)
        
    Returns:
        AdvisorRecommendation with amount, reason, and portfolio snapshot
    """
    if not historical_prices:
        logger.warning("No historical data provided for recommendation")
        return _create_recommendation(
            amount=0.0,
            reason="No historical data available for analysis.",
            holdings=current_holdings,
            cash=cash_balance,
            signal_type="HOLD"
        )
    
    try:
        # Ensure historical prices are sorted
        sorted_prices = sorted(historical_prices, key=lambda hp: hp.date)
        
        # Get latest price data
        latest_price_data = sorted_prices[-1]
        current_close = latest_price_data.close
        latest_date = latest_price_data.date
        
        if current_close <= 0:
            logger.error(f"Invalid closing price: {current_close}")
            return _create_recommendation(
                amount=0.0,
                reason="Invalid price data.",
                holdings=current_holdings,
                cash=cash_balance,
                signal_type="HOLD"
            )
        
        # Calculate RSI
        closes = [hp.close for hp in sorted_prices]
        rsi_values = calculate_rsi(closes, period=14)
        
        # Get the most recent valid RSI value
        current_rsi = None
        for rsi_val in reversed(rsi_values):
            if rsi_val is not None:
                current_rsi = rsi_val
                break
        
        if current_rsi is None:
            logger.warning("Could not calculate RSI from available data")
            return _create_recommendation(
                amount=sip_amount,  # Default to regular SIP if no RSI
                reason=f"Insufficient data for RSI calculation. Recommending regular SIP at ₹{sip_amount:.2f}.",
                holdings=current_holdings,
                cash=cash_balance,
                last_price=current_close,
                signal_type="SIP"
            )
        
        # Optional: Calculate MA20 for additional context
        ma_values = calculate_ma(closes, period=20)
        current_ma20 = None
        for ma_val in reversed(ma_values):
            if ma_val is not None:
                current_ma20 = ma_val
                break
        
        # Generate recommendation based on RSI
        recommended_amount, reason, signal_type = _generate_rsi_recommendation(
            current_rsi=current_rsi,
            current_close=current_close,
            current_ma20=current_ma20,
            sip_amount=sip_amount,
            dip_multiplier=dip_multiplier,
            cash_balance=cash_balance
        )
        
        # Create portfolio snapshot
        portfolio_snapshot = {
            "current_holdings": current_holdings,
            "cash_balance": cash_balance,
            "last_close_price": current_close,
            "last_price_date": str(latest_date),
            "current_rsi": round(current_rsi, 2)
        }
        
        if current_ma20 is not None:
            portfolio_snapshot["current_ma20"] = round(current_ma20, 2)
            portfolio_snapshot["price_vs_ma20"] = "below" if current_close < current_ma20 else "above"
        
        logger.info(
            f"Recommendation generated: Amount={recommended_amount:.2f}, "
            f"RSI={current_rsi:.2f}, Signal={signal_type}"
        )
        
        return AdvisorRecommendation(
            recommended_amount=recommended_amount,
            reason=reason,
            portfolio_state_snapshot=portfolio_snapshot,
            rsi_value=round(current_rsi, 2),
            signal_type=signal_type
        )
        
    except Exception as e:
        logger.error(f"Error generating recommendation: {e}", exc_info=True)
        return _create_recommendation(
            amount=0.0,
            reason="Error analyzing market data. Please try again.",
            holdings=current_holdings,
            cash=cash_balance,
            signal_type="HOLD"
        )


def _generate_rsi_recommendation(
    current_rsi: float,
    current_close: float,
    current_ma20: Optional[float],
    sip_amount: float,
    dip_multiplier: float,
    cash_balance: float
) -> tuple[float, str, str]:
    """
    Generate recommendation based on RSI and MA analysis.
    
    Args:
        current_rsi: Current RSI value
        current_close: Current closing price
        current_ma20: Current 20-day MA (optional)
        sip_amount: Regular SIP amount
        dip_multiplier: Dip buy multiplier
        cash_balance: Available cash
        
    Returns:
        Tuple of (recommended_amount, reason, signal_type)
    """
    # Extreme oversold condition - RSI < 20
    if current_rsi < RSI_EXTREME_OVERSOLD:
        # Recommend 2x dip buy for extreme oversold
        multiplier = max(2.0, dip_multiplier)
        buy_amount = min(sip_amount * multiplier, cash_balance)
        
        if current_ma20 and current_close < current_ma20:
            reason = (
                f"🔴 EXTREME OVERSOLD signal (RSI: {current_rsi:.1f}). "
                f"Price is below MA20 (₹{current_ma20:.2f}). "
                f"Strong buying opportunity - recommend {multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        else:
            reason = (
                f"🔴 EXTREME OVERSOLD signal (RSI: {current_rsi:.1f}). "
                f"Strong buying opportunity - recommend {multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        
        return buy_amount, reason, "DIP_BUY"
    
    # Strong oversold condition - RSI < 25
    elif current_rsi < RSI_STRONG_OVERSOLD:
        # Recommend 1.5x dip buy for strong oversold
        multiplier = max(1.5, dip_multiplier)
        buy_amount = min(sip_amount * multiplier, cash_balance)
        
        if current_ma20 and current_close < current_ma20:
            reason = (
                f"🟠 Strong oversold signal (RSI: {current_rsi:.1f}). "
                f"Price is below MA20 (₹{current_ma20:.2f}). "
                f"Good buying opportunity - recommend {multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        else:
            reason = (
                f"🟠 Strong oversold signal (RSI: {current_rsi:.1f}). "
                f"Good buying opportunity - recommend {multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        
        return buy_amount, reason, "DIP_BUY"
    
    # Oversold condition - RSI < 30
    elif current_rsi < RSI_OVERSOLD:
        buy_amount = min(sip_amount * dip_multiplier, cash_balance)
        
        if current_ma20 and current_close < current_ma20:
            reason = (
                f"🟡 Oversold signal (RSI: {current_rsi:.1f}). "
                f"Price is below MA20 (₹{current_ma20:.2f}). "
                f"Dip buying opportunity - recommend {dip_multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        else:
            reason = (
                f"🟡 Oversold signal (RSI: {current_rsi:.1f}). "
                f"Moderate buying opportunity - recommend {dip_multiplier:.1f}x SIP at ₹{buy_amount:.2f}."
            )
        
        return buy_amount, reason, "DIP_BUY"
    
    # Overbought condition - RSI > 70
    elif current_rsi > RSI_OVERBOUGHT:
        reason = (
            f"🔵 Overbought signal (RSI: {current_rsi:.1f}). "
            f"Market is overvalued. Recommend holding current positions and waiting for better entry."
        )
        
        return 0.0, reason, "HOLD"
    
    # Normal condition - RSI between 30 and 70
    else:
        if current_ma20:
            if current_close < current_ma20:
                reason = (
                    f"🟢 Neutral RSI ({current_rsi:.1f}). "
                    f"Price below MA20 (₹{current_ma20:.2f}). "
                    f"Recommend regular SIP at ₹{sip_amount:.2f}."
                )
            else:
                reason = (
                    f"🟢 Neutral RSI ({current_rsi:.1f}). "
                    f"Price above MA20 (₹{current_ma20:.2f}). "
                    f"Recommend regular SIP at ₹{sip_amount:.2f}."
                )
        else:
            reason = (
                f"🟢 Neutral market conditions (RSI: {current_rsi:.1f}). "
                f"Recommend regular SIP at ₹{sip_amount:.2f}."
            )
        
        return sip_amount, reason, "SIP"


def _create_recommendation(
    amount: float,
    reason: str,
    holdings: Dict[str, float],
    cash: float,
    signal_type: str,
    last_price: Optional[float] = None,
    rsi: Optional[float] = None
) -> AdvisorRecommendation:
    """
    Helper to create AdvisorRecommendation with consistent structure.
    
    Args:
        amount: Recommended investment amount
        reason: Explanation for recommendation
        holdings: Current holdings
        cash: Cash balance
        signal_type: Signal type (SIP, DIP_BUY, HOLD)
        last_price: Optional last closing price
        rsi: Optional RSI value
        
    Returns:
        AdvisorRecommendation object
    """
    snapshot = {
        "current_holdings": holdings,
        "cash_balance": cash
    }
    
    if last_price is not None:
        snapshot["last_close_price"] = last_price
    
    if rsi is not None:
        snapshot["current_rsi"] = round(rsi, 2)
    
    return AdvisorRecommendation(
        recommended_amount=amount,
        reason=reason,
        portfolio_state_snapshot=snapshot,
        rsi_value=round(rsi, 2) if rsi is not None else None,
        signal_type=signal_type
    )