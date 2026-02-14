import pytest
from datetime import date, timedelta
from typing import List, Optional
from unittest.mock import MagicMock

from app.strategy.backtest_engine import run_backtest
from app.strategy.models import StrategyInput, StrategyResult, SummaryStatistics, DailyPortfolioValue, TransactionRecord
from app.db.models import HistoricalPrice

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
    # Mocking model_dump for Pydantic compatibility in backtest_engine
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

def test_run_backtest_empty_data():
    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="NIFTYBEES", start_date=date(2023, 1, 1), end_date=date(2023, 1, 31)
    )
    result = run_backtest([], strategy_input)
    assert result.equity_curve == []
    assert result.transactions == []
    assert result.summary_stats.total_investment == 0
    assert result.summary_stats.final_portfolio_value == 0
    assert result.summary_stats.absolute_return == 0
    assert "No historical data found" in result.message

def test_run_backtest_basic_sip():
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 31)
    prices = [
        create_mock_historical_price("2023-01-01", 100),
        create_mock_historical_price("2023-01-02", 101),
        create_mock_historical_price("2023-01-03", 102), # SIP day
        create_mock_historical_price("2023-01-04", 103),
        create_mock_historical_price("2023-01-05", 104),
        create_mock_historical_price("2023-01-06", 105),
        create_mock_historical_price("2023-01-15", 110),
        create_mock_historical_price("2023-01-31", 115),
    ]

    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="TESTETF", start_date=start_date, end_date=end_date,
        sip_amount=1000
    )
    result = run_backtest(prices, strategy_input)

    assert result.summary_stats.total_investment == 1000 # One SIP
    assert result.transactions[0].type == "SIP"
    assert result.transactions[0].amount == 1000
    assert result.transactions[0].date == date(2023, 1, 3) # SIP should be on 3rd Jan (first 5 days)

    # Check equity curve has values
    assert len(result.equity_curve) > 0
    assert result.equity_curve[0].date == start_date
    assert result.equity_curve[-1].date == end_date
    assert result.summary_stats.final_portfolio_value > 0

def test_run_backtest_rsi_ma20_buy_condition():
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 31)
    
    # Prices designed to trigger a buy: RSI < 30 and Close < MA20
    # Simulate a dip
    prices = [
        create_mock_historical_price("2023-01-01", 100), create_mock_historical_price("2023-01-02", 101),
        create_mock_historical_price("2023-01-03", 102), create_mock_historical_price("2023-01-04", 103),
        create_mock_historical_price("2023-01-05", 104), create_mock_historical_price("2023-01-06", 105),
        create_mock_historical_price("2023-01-07", 106), create_mock_historical_price("2023-01-08", 107),
        create_mock_historical_price("2023-01-09", 108), create_mock_historical_price("2023-01-10", 109),
        create_mock_historical_price("2023-01-11", 110), create_mock_historical_price("2023-01-12", 111),
        create_mock_historical_price("2023-01-13", 112), create_mock_historical_price("2023-01-14", 113), # RSI calc starts here
        create_mock_historical_price("2023-01-15", 110), create_mock_historical_price("2023-01-16", 105), # Dip starts
        create_mock_historical_price("2023-01-17", 100), # Assume RSI < 30 and Close < MA20 here
        create_mock_historical_price("2023-01-18", 101),
        create_mock_historical_price("2023-01-31", 120),
    ]

    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="TESTETF", start_date=start_date, end_date=end_date,
        sip_amount=1000, dip_multiplier=1.0
    )
    result = run_backtest(prices, strategy_input)
    
    # Expect at least one SIP and one BUY transaction
    assert any(t.type == "SIP" for t in result.transactions)
    assert any(t.type == "BUY" for t in result.transactions)

    # Check that total investment is higher due to a buy
    initial_sip_amount = 1000 # For one month
    assert result.summary_stats.total_investment > initial_sip_amount
    assert result.summary_stats.final_portfolio_value > 0

def test_run_backtest_xirr_calculation():
    start_date = date(2023, 1, 1)
    end_date = date(2023, 12, 31)
    # Simulate monthly SIPs and a final value
    prices = [create_mock_historical_price(f"2023-{m:02d}-03", 100 + m) for m in range(1, 13)] # SIP days
    prices.extend([create_mock_historical_price(f"2023-{m:02d}-15", 100 + m + 5) for m in range(1, 13)]) # other days
    prices.append(create_mock_historical_price("2023-12-31", 150)) # Final price

    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="TESTETF", start_date=start_date, end_date=end_date,
        sip_amount=1000
    )
    result = run_backtest(prices, strategy_input)

    assert result.summary_stats.xirr is not None
    # XIRR calculation is approx, so check if it's within a reasonable range
    assert -0.5 < result.summary_stats.xirr < 0.5 # Should be some positive or negative return, not zero or extreme.

def test_run_backtest_with_benchmark():
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 31)
    prices = [create_mock_historical_price(f"2023-01-{d:02d}", 100 + d) for d in range(1, 32)]
    benchmark_prices = [create_mock_historical_price(f"2023-01-{d:02d}", 90 + d) for d in range(1, 32)]

    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="TESTETF", start_date=start_date, end_date=end_date,
        sip_amount=1000, benchmark_index="NIFTY50"
    )
    result = run_backtest(prices, strategy_input, benchmark_data=benchmark_prices)

    assert result.benchmark_curve is not None
    assert len(result.benchmark_curve) > 0
    assert result.summary_stats.benchmark_return is not None
    assert result.summary_stats.benchmark_return != 0 # Should have some return

def test_run_backtest_carry_over_fraction():
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 31)
    # Prices: SIP on 3rd, then a dip on 17th
    prices = [
        create_mock_historical_price("2023-01-01", 100), create_mock_historical_price("2023-01-02", 101),
        create_mock_historical_price("2023-01-03", 102), # SIP day
        create_mock_historical_price("2023-01-04", 103),
        create_mock_historical_price("2023-01-05", 104),
        create_mock_historical_price("2023-01-06", 105),
        create_mock_historical_price("2023-01-07", 106), create_mock_historical_price("2023-01-08", 107),
        create_mock_historical_price("2023-01-09", 108), create_mock_historical_price("2023-01-10", 109),
        create_mock_historical_price("2023-01-11", 110), create_mock_historical_price("2023-01-12", 111),
        create_mock_historical_price("2023-01-13", 112), create_mock_historical_price("2023-01-14", 113),
        create_mock_historical_price("2023-01-15", 110), create_mock_historical_price("2023-01-16", 105),
        create_mock_historical_price("2023-01-17", 100, adj_close=100), # Dip day - assume RSI < 30 and Close < MA20
        create_mock_historical_price("2023-01-18", 101),
        create_mock_historical_price("2023-01-31", 120),
    ]

    strategy_input = StrategyInput(
        instrument_type="ETF", symbol="TESTETF", start_date=start_date, end_date=end_date,
        sip_amount=1000, dip_multiplier=1.0, carry_over_fraction=0.5
    )
    result = run_backtest(prices, strategy_input)
    
    # Verify that cash balance is managed and some amount might be carried over if not fully invested.
    # This test is more about ensuring the logic doesn't crash and behaves reasonably.
    # More detailed assertions would require complex state tracking.
    assert result.summary_stats.final_portfolio_value > 0
    assert result.summary_stats.total_investment >= 1000 # At least one SIP
