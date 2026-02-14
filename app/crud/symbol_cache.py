from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import SymbolCache
from app.schemas.instrument import SymbolCacheCreate

class CRUDSymbolCache:
    def get(self, db: Session, symbol_cache_id: UUID) -> Optional[SymbolCache]:
        return db.query(SymbolCache).filter(SymbolCache.id == symbol_cache_id).first()

    def get_by_symbol(self, db: Session, symbol: str) -> Optional[SymbolCache]:
        return db.query(SymbolCache).filter(SymbolCache.symbol == symbol).first()

    def get_multi_by_partial_symbol(self, db: Session, partial_symbol: str, skip: int = 0, limit: int = 100) -> List[SymbolCache]:
        return db.query(SymbolCache).filter(SymbolCache.symbol.ilike(f"%{partial_symbol}%")).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: SymbolCacheCreate) -> SymbolCache:
        db_obj = SymbolCache(
            symbol=obj_in.symbol,
            name=obj_in.name,
            instrument_type=obj_in.instrument_type,
            source=obj_in.source
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

symbol_cache = CRUDSymbolCache()