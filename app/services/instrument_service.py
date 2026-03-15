import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.db.models import Instrument
from app.schemas.instrument import InstrumentCreate

logger = logging.getLogger(__name__)


class InstrumentService:
    """Service for managing instruments (stocks, ETFs, indices, mutual funds)."""
    
    def get_instrument_by_symbol(self, db: Session, symbol: str) -> Optional[Instrument]:
        """Get instrument by symbol."""
        if not symbol or not symbol.strip():
            logger.warning("Empty symbol provided")
            return None
        
        return crud_instrument.get_by_symbol(db, symbol.strip().upper())
    
    def search_instruments(
        self,
        db: Session,
        query: str,
        instrument_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Instrument]:
        """
        Search instruments by partial symbol or name match.
        
        This replaces the old symbol_cache search functionality.
        """
        if not query or not query.strip():
            logger.warning("Empty search query")
            return []
        
        query = query.strip()
        
        # Validate instrument type
        if instrument_type and instrument_type not in ['EQUITY', 'ETF', 'INDEX', 'MF']:
            logger.warning(f"Invalid instrument type: {instrument_type}")
            return []
        
        # Enforce limit bounds
        limit = max(1, min(limit, 100))
        
        # Search in database
        instruments = crud_instrument.search_by_symbol_or_name(
            db,
            query=query,
            instrument_type=instrument_type,
            limit=limit
        )
        
        logger.info(f"Search for '{query}' (type: {instrument_type}): found {len(instruments)} results")
        return instruments
    
    def create_or_get_instrument(
        self,
        db: Session,
        symbol: str,
        name: str,
        instrument_type: str
    ) -> Instrument:
        """
        Create instrument if it doesn't exist, otherwise return existing.
        Used when caching search results.
        """
        symbol = symbol.strip().upper()
        
        # Check if exists
        existing = crud_instrument.get_by_symbol(db, symbol)
        if existing:
            return existing
        
        # Create new
        instrument_create = InstrumentCreate(
            symbol=symbol,
            name=name,
            instrument_type=instrument_type
        )
        
        try:
            return crud_instrument.create(db, obj_in=instrument_create)
        except Exception as e:
            logger.error(f"Error creating instrument {symbol}: {e}")
            # If creation failed (e.g., duplicate), try to get it again
            db.rollback()
            return crud_instrument.get_by_symbol(db, symbol)


instrument_service = InstrumentService()