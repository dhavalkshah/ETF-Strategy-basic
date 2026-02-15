import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.crud.symbol_cache import symbol_cache as crud_symbol_cache
from app.schemas.instrument import InstrumentCreate, SymbolCacheCreate, InstrumentOut, SymbolCacheOut
from app.db.models import Instrument, SymbolCache
from app.services.data_service import data_service

logger = logging.getLogger(__name__)


class InstrumentService:
    """
    Service for managing instruments and symbol lookups.
    
    Handles instrument CRUD operations and symbol search with caching.
    """
    
    MAX_SEARCH_LIMIT = 100  # Maximum symbols to return in search
    
    def get_instrument_by_symbol(self, db: Session, symbol: str) -> Optional[InstrumentOut]:
        """
        Retrieves an instrument by its symbol.
        
        Args:
            db: Database session
            symbol: Instrument symbol to search for
            
        Returns:
            InstrumentOut if found, None otherwise
        """
        if not symbol or not symbol.strip():
            logger.warning("get_instrument_by_symbol called with empty symbol")
            return None
        
        try:
            db_instrument = crud_instrument.get_by_symbol(db, symbol.strip().upper())
            if db_instrument:
                return InstrumentOut.model_validate(db_instrument)
            return None
        except Exception as e:
            logger.error(f"Error fetching instrument {symbol}: {e}")
            return None

    def create_instrument(self, db: Session, instrument_in: InstrumentCreate) -> Optional[InstrumentOut]:
        """
        Creates a new instrument.
        
        Args:
            db: Database session
            instrument_in: Instrument creation data
            
        Returns:
            InstrumentOut if created successfully, None on error
        """
        try:
            # Normalize symbol to uppercase
            if instrument_in.symbol:
                instrument_in.symbol = instrument_in.symbol.strip().upper()
            
            db_instrument = crud_instrument.create(db, obj_in=instrument_in)
            logger.info(f"Created instrument: {db_instrument.symbol}")
            return InstrumentOut.model_validate(db_instrument)
        except Exception as e:
            logger.error(f"Error creating instrument {instrument_in.symbol}: {e}")
            return None

    async def search_symbols(
        self,
        db: Session,
        query: str,
        instrument_type: Optional[str] = None,
        limit: int = 50
    ) -> List[SymbolCacheOut]:
        """
        Searches for symbols with caching support.
        
        First checks local cache, then queries live data sources if needed.
        
        Args:
            db: Database session
            query: Search query string
            instrument_type: Optional filter by type ('EQUITY', 'ETF', 'INDEX', 'MF')
            limit: Maximum number of results (default 50, max 100)
            
        Returns:
            List of matching symbols as SymbolCacheOut objects
        """
        # Validate and sanitize inputs
        if not query or not query.strip():
            logger.warning("search_symbols called with empty query")
            return []
        
        query = query.strip()
        
        # Enforce limit bounds
        limit = min(max(1, limit), self.MAX_SEARCH_LIMIT)
        
        # Validate instrument_type if provided
        valid_types = ["EQUITY", "ETF", "INDEX", "MF"]
        if instrument_type and instrument_type not in valid_types:
            logger.warning(
                f"Invalid instrument_type: {instrument_type}. "
                f"Valid types: {valid_types}"
            )
            return []
        
        try:
            # 1. First, try to find in local symbol_cache
            cached_symbols = crud_symbol_cache.get_multi_by_partial_symbol(
                db, query, limit=limit
            )
            
            # Filter by instrument_type if provided
            if instrument_type:
                cached_symbols = [
                    s for s in cached_symbols 
                    if s.instrument_type == instrument_type
                ]
            
            if cached_symbols:
                logger.info(
                    f"Returning {len(cached_symbols)} cached symbols for '{query}' "
                    f"(type: {instrument_type})"
                )
                return [SymbolCacheOut.model_validate(s) for s in cached_symbols]
            
            # 2. If not found in cache, fetch from live data sources
            logger.info(
                f"No cached symbols found for '{query}'. "
                f"Attempting live search (type: {instrument_type})."
            )
            
            live_symbols_db_models = await data_service.search_and_cache_symbols(
                db, query, instrument_type
            )
            
            if not live_symbols_db_models:
                logger.info(
                    f"No symbols found in live search for '{query}' "
                    f"(type: {instrument_type})"
                )
                return []
            
            # Apply limit to live results
            limited_results = live_symbols_db_models[:limit]
            
            logger.info(
                f"Found {len(limited_results)} symbols from live search for '{query}'"
            )
            
            return [SymbolCacheOut.model_validate(s) for s in limited_results]
            
        except Exception as e:
            logger.error(f"Error searching symbols for '{query}': {e}")
            return []

    def add_symbol_to_cache(
        self,
        db: Session,
        symbol_data: SymbolCacheCreate
    ) -> Optional[SymbolCacheOut]:
        """
        Manually adds a symbol to the cache.
        
        Args:
            db: Database session
            symbol_data: Symbol data to cache
            
        Returns:
            SymbolCacheOut if added successfully, None on error
        """
        try:
            # Normalize symbol to uppercase
            if symbol_data.symbol:
                symbol_data.symbol = symbol_data.symbol.strip().upper()
            
            # Check if already exists
            existing = crud_symbol_cache.get_by_symbol(db, symbol_data.symbol)
            if existing:
                logger.warning(
                    f"Symbol {symbol_data.symbol} already exists in cache. "
                    f"Returning existing entry."
                )
                return SymbolCacheOut.model_validate(existing)
            
            db_symbol = crud_symbol_cache.create(db, obj_in=symbol_data)
            logger.info(f"Added symbol to cache: {db_symbol.symbol}")
            return SymbolCacheOut.model_validate(db_symbol)
            
        except Exception as e:
            logger.error(f"Error adding symbol to cache {symbol_data.symbol}: {e}")
            return None


# Singleton instance
instrument_service = InstrumentService()