from fastapi import status
from fastapi.testclient import TestClient
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.db.models import HistoricalPrice
from app.services.data_service import data_service # Import the service to patch

# Helper to create mock HistoricalPrice objects (similar to unit tests)
def create_mock_historical_price_for_service(date_obj: date, close: float, adj_close: Optional[float] = None, open_price: float = 0, high_price: float = 0, low_price: float = 0, volume: int = 0) -> HistoricalPrice:
    hp = HistoricalPrice(
        id=None, # Will be set by ORM
        instrument_id=None, # Will be set by ORM
        date=date_obj,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close,
        adjusted_close=adj_close if adj_close is not None else close,
        volume=volume,
        created_at=None, updated_at=None # Will be set by ORM
    )
    return hp


@pytest.fixture
def mock_historical_data():
    """Fixture to provide mock historical data."""
    today = date.today()
    return [
        create_mock_historical_price_for_service(today - timedelta(days=i), 100 + i)
        for i in range(30, 0, -1) # Prices increasing
    ]

@pytest.fixture
def mock_benchmark_data():
    """Fixture to provide mock benchmark data."""
    today = date.today()
    return [
        create_mock_historical_price_for_service(today - timedelta(days=i), 90 + i)
        for i in range(30, 0, -1) # Prices increasing
    ]

@pytest.mark.asyncio
async def test_run_backtest_authenticated_success(authorized_client: TestClient, mock_historical_data, mock_benchmark_data):
    with patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        mock_get_historical_data.side_effect = [
            mock_historical_data, # For the main instrument
            mock_benchmark_data   # For the benchmark instrument
        ]

        strategy_input = {
            "instrument_type": "ETF",
            "symbol": "NIFTYBEES",
            "sip_amount": 1000,
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today() - timedelta(days=1)),
            "benchmark_index": "NIFTY50",
            "dip_multiplier": 1.0,
            "carry_over_fraction": 0.5
        }

        response = authorized_client.post(
            "/api/v1/backtest/",
            json=strategy_input
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "equity_curve" in data
        assert "benchmark_curve" in data
        assert "transactions" in data
        assert "summary_stats" in data
        assert data["summary_stats"]["final_portfolio_value"] > 0
        assert mock_get_historical_data.call_count == 2 # Called for instrument and benchmark

@pytest.mark.asyncio
async def test_run_backtest_authenticated_no_benchmark(authorized_client: TestClient, mock_historical_data):
    with patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        mock_get_historical_data.return_value = mock_historical_data # Only for the main instrument

        strategy_input = {
            "instrument_type": "ETF",
            "symbol": "NIFTYBEES",
            "sip_amount": 1000,
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today() - timedelta(days=1)),
            "dip_multiplier": 1.0,
            "carry_over_fraction": 0.5
        }

        response = authorized_client.post(
            "/api/v1/backtest/",
            json=strategy_input
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "equity_curve" in data
        assert data["benchmark_curve"] == [] # Should be empty
        assert "transactions" in data
        assert "summary_stats" in data
        assert data["summary_stats"]["final_portfolio_value"] > 0
        assert mock_get_historical_data.call_count == 1 # Only called for instrument

@pytest.mark.asyncio
async def test_run_backtest_unauthenticated(client: TestClient):
    strategy_input = {
        "instrument_type": "ETF",
        "symbol": "NIFTYBEES",
        "sip_amount": 1000,
        "start_date": str(date.today() - timedelta(days=30)),
        "end_date": str(date.today() - timedelta(days=1)),
    }
    response = client.post(
        "/api/v1/backtest/",
        json=strategy_input
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_run_backtest_invalid_instrument_type(authorized_client: TestClient):
    strategy_input = {
        "instrument_type": "INVALID",
        "symbol": "NIFTYBEES",
        "sip_amount": 1000,
        "start_date": str(date.today() - timedelta(days=30)),
        "end_date": str(date.today() - timedelta(days=1)),
    }
    response = authorized_client.post(
        "/api/v1/backtest/",
        json=strategy_input
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid instrument_type" in response.json()["detail"]

@pytest.mark.asyncio
async def test_run_backtest_no_historical_data_returned(authorized_client: TestClient):
    with patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        mock_get_historical_data.return_value = [] # No data returned

        strategy_input = {
            "instrument_type": "ETF",
            "symbol": "NONEXISTENT",
            "sip_amount": 1000,
            "start_date": str(date.today() - timedelta(days=30)),
            "end_date": str(date.today() - timedelta(days=1)),
        }

        response = authorized_client.post(
            "/api/v1/backtest/",
            json=strategy_input
        )
        
        assert response.status_code == status.HTTP_200_OK # Success, but with empty results
        data = response.json()
        assert data["equity_curve"] == []
        assert data["summary_stats"]["absolute_return"] == 0
        assert "No historical data found" in data["message"]