from typing import List, Optional, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.schemas.instrument import SymbolCacheOut
from app.services.instrument_service import instrument_service

router = APIRouter()

@router.get("/search", response_model=List[SymbolCacheOut], status_code=status.HTTP_200_OK)
async def search_instruments(
    query: str = Query(..., min_length=2, description="Partial symbol or name to search for"),
    instrument_type: Optional[str] = Query(None, description="Filter by instrument type (ETF, MF, INDEX)"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    # Validate instrument_type if provided
    if instrument_type and instrument_type not in ["ETF", "MF", "INDEX"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instrument_type. Must be 'ETF', 'MF', or 'INDEX'."
        )
    
    symbols = await instrument_service.search_symbols(db, query, instrument_type, limit)
    return symbols