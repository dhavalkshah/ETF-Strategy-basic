from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import Instrument
from app.schemas.instrument import InstrumentCreate, InstrumentUpdate


class CRUDInstrument:
    """CRUD operations for Instrument model."""
    
    def get(self, db: Session, id: UUID) -> Optional[Instrument]:
        """Get instrument by ID."""
        return db.query(Instrument).filter(Instrument.id == id).first()
    
    def get_by_symbol(self, db: Session, symbol: str) -> Optional[Instrument]:
        """Get instrument by symbol (case-insensitive)."""
        return db.query(Instrument).filter(
            Instrument.symbol == symbol.upper()
        ).first()
    
    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[Instrument]:
        """Get multiple instruments."""
        return db.query(Instrument).offset(skip).limit(limit).all()
    
    def create(self, db: Session, obj_in: InstrumentCreate) -> Instrument:
        """Create new instrument."""
        db_obj = Instrument(
            symbol=obj_in.symbol.upper(),
            name=obj_in.name,
            instrument_type=obj_in.instrument_type
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self,
        db: Session,
        db_obj: Instrument,
        obj_in: InstrumentUpdate
    ) -> Instrument:
        """Update instrument."""
        update_data = obj_in.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == 'symbol' and value:
                value = value.upper()
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, id: UUID) -> Instrument:
        """Delete instrument."""
        obj = db.query(Instrument).filter(Instrument.id == id).first()
        db.delete(obj)
        db.commit()
        return obj
    
    def search_by_symbol_or_name(
        self,
        db: Session,
        query: str,
        instrument_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Instrument]:
        """
        Search instruments by partial match on symbol or name.
        
        Args:
            db: Database session
            query: Search query (partial match)
            instrument_type: Optional filter by type
            limit: Maximum results to return
            
        Returns:
            List of matching instruments
        """
        query_upper = query.upper()
        
        # Build query with OR condition for symbol and name
        db_query = db.query(Instrument).filter(
            or_(
                Instrument.symbol.ilike(f"%{query_upper}%"),
                Instrument.name.ilike(f"%{query}%")
            )
        )
        
        # Filter by type if specified
        if instrument_type:
            db_query = db_query.filter(Instrument.instrument_type == instrument_type)
        
        # Order by relevance:
        # 1. Exact symbol match first
        # 2. Symbol starts with query
        # 3. Then alphabetically
        db_query = db_query.order_by(
            # Exact match first
            (Instrument.symbol != query_upper).asc(),
            # Starts with query second
            (~Instrument.symbol.startswith(query_upper)).asc(),
            # Then alphabetically
            Instrument.symbol.asc()
        )
        
        return db_query.limit(limit).all()
    
    def get_multi_by_type(
        self,
        db: Session,
        instrument_type: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Instrument]:
        """Get instruments by type."""
        return (
            db.query(Instrument)
            .filter(Instrument.instrument_type == instrument_type)
            .offset(skip)
            .limit(limit)
            .all()
        )


instrument = CRUDInstrument()