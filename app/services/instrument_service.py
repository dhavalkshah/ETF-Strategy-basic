import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.crud.instrument import instrument as crud_instrument
from app.crud.symbol_cache import symbol_cache as crud_symbol_cache
from app.schemas.instrument import InstrumentCreate, SymbolCacheCreate, InstrumentOut, SymbolCacheOut
from app.db.models import Instrument, SymbolCache
from app.services.data_service import data_service # Import data_service

logger = logging.getLogger(__name__)

class InstrumentService:
    def get_instrument_by_symbol(self, db: Session, symbol: str) -> Optional[InstrumentOut]:
        db_instrument = crud_instrument.get_by_symbol(db, symbol)
        if db_instrument:
            return InstrumentOut.model_validate(db_instrument)
        return None

    def create_instrument(self, db: Session, instrument_in: InstrumentCreate) -> InstrumentOut:
        db_instrument = crud_instrument.create(db, obj_in=instrument_in)
        return InstrumentOut.model_validate(db_instrument)

    async def search_symbols(self, db: Session, query: str, instrument_type: Optional[str] = None, limit: int = 100) -> List[SymbolCacheOut]:
        # 1. First, try to find in local symbol_cache
        cached_symbols = crud_symbol_cache.get_multi_by_partial_symbol(db, query, limit=limit)
        
        if instrument_type:
            cached_symbols = [s for s in cached_symbols if s.instrument_type == instrument_type]

        if cached_symbols:
            logger.info(f"Returning {len(cached_symbols)} cached symbols for '{query}' (type: {instrument_type})")
            return [SymbolCacheOut.model_validate(s) for s in cached_symbols]
        
        # 2. If not found in cache, fetch from live data sources and cache them
        logger.info(f"No cached symbols found for '{query}'. Attempting live search.")
        live_symbols_db_models = await data_service.search_and_cache_symbols(db, query, instrument_type)
        
        return [SymbolCacheOut.model_validate(s) for s in live_symbols_db_models]

    def add_symbol_to_cache(self, db: Session, symbol_data: SymbolCacheCreate) -> SymbolCacheOut:
        db_symbol = crud_symbol_cache.create(db, obj_in=symbol_data)
        return SymbolCacheOut.model_validate(db_symbol)

instrument_service = InstrumentService()