import pytest
from datetime import date, timedelta
from typing import List, Dict, Any

from app.strategy.advisor_logic import get_advisor_recommendation
from app.strategy.models import AdvisorRecommendation
from app.db.models import HistoricalPrice # Assuming HistoricalPrice is imported

# Helper to create mock HistoricalPrice objects
def create_mock_historical_price(date_str: str, close: float, adj_close: Optional[float] = None, open_price: float = 0, high_price: float = 0, low_price: float = 0, volume: int = 0) -> HistoricalPrice:
    hp = HistoricalPrice(
        id=None, # Will be set by ORM
        instrument_id=None, # Will be set by ORM
        date=date.fromisoformat(date_str),
        open=open_price,
        high=high_price,
        low=low_price,
        close=close,
        adjusted_close=adj_close if adj_close is not None else close,
        volume=volume,
        created_at=None, updated_at=None # Will be set by ORM
    )
    # Mocking model_dump for Pydantic compatibility if needed
    hp.model_dump = lambda: {
        "date": hp.date,
        "close": hp.close,
        "adjusted_close": hp.adjusted_close,
        "open": hp.open,
        "high": hp.high,
        "low": hp.low,
        "volume": hp.volume
    }
    return hp

def test_get_advisor_recommendation_no_historical_data():
    current_holdings = {"NIFTYBEES": 10.0}
    cash_balance = 5000.0
    sip_amount = 1000.0
    dip_multiplier = 1.0
    historical_prices = []

    recommendation = get_advisor_recommendation(
        current_holdings=current_holdings,
        cash_balance=cash_balance,
        historical_prices=historical_prices,
        sip_amount=sip_amount,
        dip_multiplier=dip_multiplier
    )

    assert recommendation.recommended_amount == 0.0
    assert "No historical data available" in recommendation.reason

def test_get_advisor_recommendation_low_rsi_buy():
    # Create historical data that would result in a low RSI
    today = date.today()
    prices_data = []
    # Simulate a strong downward trend to get low RSI
    for i in range(30, 0, -1):
        prices_data.append(create_mock_historical_price(str(today - timedelta(days=i)), 100 + (i * 0.5))) # Prices dropping
    prices_data.append(create_mock_historical_price(str(today), 90.0)) # A further drop to make RSI low

    current_holdings = {"NIFTYBEES": 10.0}
    cash_balance = 5000.0
    sip_amount = 1000.0
    dip_multiplier = 1.5 # Allow buying 1.5x SIP amount

    recommendation = get_advisor_recommendation(
        current_holdings=current_holdings,
        cash_balance=cash_balance,
        historical_prices=prices_data,
        sip_amount=sip_amount,
        dip_multiplier=dip_multiplier
    )
    
    assert recommendation.recommended_amount == pytest.approx(1000.0 * 1.5) # Expect a dip buy
    assert "RSI is low" in recommendation.reason
    assert recommendation.portfolio_state_snapshot["current_rsi"] < 30

def test_get_advisor_recommendation_normal_rsi_no_buy():
    # Create historical data that would result in a normal RSI
    today = date.today()
    prices_data = []
    # Simulate stable prices
    for i in range(30, 0, -1):
        prices_data.append(create_mock_historical_price(str(today - timedelta(days=i)), 100))
    prices_data.append(create_mock_historical_price(str(today), 100))

    current_holdings = {"NIFTYBEES": 10.0}
    cash_balance = 5000.0
    sip_amount = 1000.0
    dip_multiplier = 1.0

    recommendation = get_advisor_recommendation(
        current_holdings=current_holdings,
        cash_balance=cash_balance,
        historical_prices=prices_data,
        sip_amount=sip_amount,
        dip_multiplier=dip_multiplier
    )

    assert recommendation.recommended_amount == 0.0
    assert "No specific recommendation" in recommendation.reason
    assert recommendation.portfolio_state_snapshot["current_rsi"] >= 30

def test_get_advisor_recommendation_not_enough_data_for_rsi():
    current_holdings = {"NIFTYBEES": 10.0}
    cash_balance = 5000.0
    sip_amount = 1000.0
    dip_multiplier = 1.0
    # Only a few data points, not enough for 14-period RSI
    historical_prices = [
        create_mock_historical_price("2023-01-01", 100),
        create_mock_historical_price("2023-01-02", 101),
        create_mock_historical_price("2023-01-03", 90),
    ]

    recommendation = get_advisor_recommendation(
        current_holdings=current_holdings,
        cash_balance=cash_balance,
        historical_prices=historical_prices,
        sip_amount=sip_amount,
        dip_multiplier=dip_multiplier
    )

    assert recommendation.recommended_amount == 0.0
    assert "Could not calculate RSI" in recommendation.reason
    assert recommendation.portfolio_state_snapshot["current_rsi"] is None