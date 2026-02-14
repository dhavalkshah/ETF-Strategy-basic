from fastapi import status
from fastapi.testclient import TestClient
import pytest
from unittest.mock import AsyncMock, patch

from app.db.models import SymbolCache
from app.services.instrument_service import instrument_service
from app.schemas.instrument import SymbolCacheOut

# Helper to create mock SymbolCache objects
def create_mock_symbol_cache(symbol: str, name: str, instrument_type: str) -> SymbolCache:
    sc = SymbolCache(
        id=None, # Will be set by ORM
        symbol=symbol,
        name=name,
        instrument_type=instrument_type,
        source="MOCKED",
        last_fetched_at=None, created_at=None, updated_at=None
    )
    return sc

@pytest.mark.asyncio
async def test_search_instruments_authenticated_cached(authorized_client: TestClient):
    mock_symbols_out = [
        SymbolCacheOut(id=str(uuid.uuid4()), symbol="NIFTYBEES", name="NIFTYBEES ETF", instrument_type="ETF", source="MOCKED", last_fetched_at=None, created_at=None, updated_at=None),
        SymbolCacheOut(id=str(uuid.uuid4()), symbol="JUNIORBEES", name="NIFTY NEXT 50 ETF", instrument_type="ETF", source="MOCKED", last_fetched_at=None, created_at=None, updated_at=None),
    ]
    with patch.object(instrument_service, 'search_symbols', new_callable=AsyncMock) as mock_search_symbols:
        mock_search_symbols.return_value = mock_symbols_out

        response = authorized_client.get(
            "/api/v1/instrument/search?query=NIFTY"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["symbol"] == "NIFTYBEES"
        assert mock_search_symbols.called_once_with("NIFTY", None, 10)

@pytest.mark.asyncio
async def test_search_instruments_authenticated_filtered_type(authorized_client: TestClient):
    mock_symbols_out = [
        SymbolCacheOut(id=str(uuid.uuid4()), symbol="HDFCMF", name="HDFC Mutual Fund", instrument_type="MF", source="MOCKED", last_fetched_at=None, created_at=None, updated_at=None),
    ]
    with patch.object(instrument_service, 'search_symbols', new_callable=AsyncMock) as mock_search_symbols:
        mock_search_symbols.return_value = mock_symbols_out

        response = authorized_client.get(
            "/api/v1/instrument/search?query=HDFC&instrument_type=MF"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "HDFCMF"
        assert data[0]["instrument_type"] == "MF"
        assert mock_search_symbols.called_once_with("HDFC", "MF", 10)

@pytest.mark.asyncio
async def test_search_instruments_unauthenticated(client: TestClient):
    response = client.get(
        "/api/v1/instrument/search?query=NIFTY"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_search_instruments_invalid_instrument_type(authorized_client: TestClient):
    response = authorized_client.get(
        "/api/v1/instrument/search?query=NIFTY&instrument_type=INVALID"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid instrument_type" in response.json()["detail"]

@pytest.mark.asyncio
async def test_search_instruments_min_query_length(authorized_client: TestClient):
    response = authorized_client.get(
        "/api/v1/instrument/search?query=N" # Too short
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY # Pydantic validation error