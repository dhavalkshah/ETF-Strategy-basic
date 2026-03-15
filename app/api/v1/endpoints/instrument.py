from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User, Instrument
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service
from app.schemas.instrument import InstrumentOut

router = APIRouter()


@router.get(
    "/search",
    response_model=List[InstrumentOut],
    status_code=status.HTTP_200_OK,
    summary="Search Instruments",
    description="Search for stocks, ETFs, indices, or mutual funds by symbol or name"
)
async def search_instruments(
    query: str = Query(..., min_length=1, description="Search query (symbol or name)"),
    instrument_type: str = Query(None, description="Filter by type: EQUITY, ETF, INDEX, or MF"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Search for instruments across multiple sources.
    
    - First checks database cache
    - If not found, searches external sources (NSE, MFAPI, etc.)
    - Caches results for future searches
    
    Returns list of matching instruments.
    """
    if instrument_type and instrument_type not in ['EQUITY', 'ETF', 'INDEX', 'MF']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instrument_type. Must be one of: EQUITY, ETF, INDEX, MF"
        )
    
    # Search and cache (uses Instrument table now, not SymbolCache)
    instruments = await data_service.search_and_cache_symbols(
        db,
        query=query,
        instrument_type=instrument_type
    )
    
    # Apply limit
    instruments = instruments[:limit]
    
    return instruments


@router.get(
    "/{symbol}",
    response_model=InstrumentOut,
    status_code=status.HTTP_200_OK,
    summary="Get Instrument by Symbol",
    description="Get details of a specific instrument by its symbol"
)
async def get_instrument(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get instrument details by symbol."""
    instrument = instrument_service.get_instrument_by_symbol(db, symbol)
    
    if not instrument:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instrument with symbol '{symbol}' not found"
        )
    
    return instrument