from fastapi import status
from fastapi.testclient import TestClient
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.db.models import HistoricalPrice, Instrument
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service

# Helper to create mock HistoricalPrice objects
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

# Helper to create mock Instrument object
def create_mock_instrument(symbol: str, instrument_type: str) -> Instrument:
    inst = Instrument(
        id=None, # Will be set by ORM
        symbol=symbol,
        name=f"{symbol} Name",
        instrument_type=instrument_type,
        isin=None, exchange=None, last_fetched_at=None, created_at=None, updated_at=None
    )
    return inst

@pytest.fixture
def mock_historical_prices_for_advisor():
    """Provides mock historical prices for advisor (simulating a dip for low RSI)."""
    today = date.today()
    prices = []
    # Simulate a strong downward trend to get low RSI on the last day
    for i in range(30, 0, -1):
        prices.append(create_mock_historical_price_for_service(today - timedelta(days=i), 100 + (i * 0.5))) # Prices dropping
    prices.append(create_mock_historical_price_for_service(today, 90.0)) # A further drop to make RSI low
    return prices

@pytest.fixture
def mock_historical_prices_for_advisor_normal_rsi():
    """Provides mock historical prices for advisor (simulating stable prices for normal RSI)."""
    today = date.today()
    prices = []
    # Simulate stable prices
    for i in range(30, 0, -1):
        prices.append(create_mock_historical_price_for_service(today - timedelta(days=i), 100))
    prices.append(create_mock_historical_price_for_service(today, 100))
    return prices

@pytest.mark.asyncio
async def test_get_advisor_recommendation_authenticated_buy(authorized_client: TestClient, mock_historical_prices_for_advisor):
    with patch.object(instrument_service, 'get_instrument_by_symbol', return_value=create_mock_instrument("NIFTYBEES", "ETF")), 
         patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        
        mock_get_historical_data.return_value = mock_historical_prices_for_advisor

        advisor_request = {
            "instrument_symbol": "NIFTYBEES",
            "current_holdings": {"NIFTYBEES": 10.0},
            "cash_balance": 5000.0,
            "sip_amount": 1000.0,
            "dip_multiplier": 1.5
        }

        response = authorized_client.post(
            "/api/v1/advisor/",
            json=advisor_request
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["recommended_amount"] > 0
        assert "RSI is low" in data["reason"]
        assert data["portfolio_state_snapshot"]["current_rsi"] < 30

@pytest.mark.asyncio
async def test_get_advisor_recommendation_authenticated_no_buy(authorized_client: TestClient, mock_historical_prices_for_advisor_normal_rsi):
    with patch.object(instrument_service, 'get_instrument_by_symbol', return_value=create_mock_instrument("NIFTYBEES", "ETF")), 
         patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        
        mock_get_historical_data.return_value = mock_historical_prices_for_advisor_normal_rsi

        advisor_request = {
            "instrument_symbol": "NIFTYBEES",
            "current_holdings": {"NIFTYBEES": 10.0},
            "cash_balance": 5000.0,
            "sip_amount": 1000.0,
            "dip_multiplier": 1.5
        }

        response = authorized_client.post(
            "/api/v1/advisor/",
            json=advisor_request
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["recommended_amount"] == 0.0
        assert "No specific recommendation" in data["reason"]
        assert data["portfolio_state_snapshot"]["current_rsi"] >= 30

@pytest.mark.asyncio
async def test_get_advisor_recommendation_unauthenticated(client: TestClient):
    advisor_request = {
        "instrument_symbol": "NIFTYBEES",
        "current_holdings": {"NIFTYBEES": 10.0},
        "cash_balance": 5000.0,
        "sip_amount": 1000.0,
        "dip_multiplier": 1.0
    }
    response = client.post(
        "/api/v1/advisor/",
        json=advisor_request
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_get_advisor_recommendation_instrument_not_found(authorized_client: TestClient):
    with patch.object(instrument_service, 'get_instrument_by_symbol', return_value=None):
        advisor_request = {
            "instrument_symbol": "NONEXISTENT",
            "current_holdings": {"NONEXISTENT": 0.0},
            "cash_balance": 5000.0,
            "sip_amount": 1000.0,
            "dip_multiplier": 1.0
        }

        response = authorized_client.post(
            "/api/v1/advisor/",
            json=advisor_request
        )
        
        assert response.status_code == status.HTTP_200_OK # Returns success, but recommendation amount is 0
        data = response.json()
        assert data["recommended_amount"] == 0.0
        assert "Instrument NONEXISTENT not found" in data["reason"]

@pytest.mark.asyncio
async def test_get_advisor_recommendation_not_enough_historical_data(authorized_client: TestClient):
    with patch.object(instrument_service, 'get_instrument_by_symbol', return_value=create_mock_instrument("NIFTYBEES", "ETF")), 
         patch.object(data_service, 'get_historical_data', new_callable=AsyncMock) as mock_get_historical_data:
        
        mock_get_historical_data.return_value = [] # Not enough historical data

        advisor_request = {
            "instrument_symbol": "NIFTYBEES",
            "current_holdings": {"NIFTYBEES": 10.0},
            "cash_balance": 5000.0,
            "sip_amount": 1000.0,
            "dip_multiplier": 1.0
        }

        response = authorized_client.post(
            "/api/v1/advisor/",
            json=advisor_request
        )
        
        assert response.status_code == status.HTTP_200_OK # Returns success, but recommendation amount is 0
        data = response.json()
        assert data["recommended_amount"] == 0.0
        assert "Not enough historical data" in data["reason"]