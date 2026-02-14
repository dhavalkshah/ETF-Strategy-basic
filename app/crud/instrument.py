from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Instrument
from app.schemas.instrument import InstrumentCreate, InstrumentUpdate

class CRUDInstrument:
    def get(self, db: Session, instrument_id: UUID) -> Optional[Instrument]:
        return db.query(Instrument).filter(Instrument.id == instrument_id).first()

    def get_by_symbol(self, db: Session, symbol: str) -> Optional[Instrument]:
        return db.query(Instrument).filter(Instrument.symbol == symbol).first()

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[Instrument]:
        return db.query(Instrument).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: InstrumentCreate) -> Instrument:
        db_obj = Instrument(
            symbol=obj_in.symbol,
            name=obj_in.name,
            instrument_type=obj_in.instrument_type,
            isin=obj_in.isin,
            exchange=obj_in.exchange
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: Instrument, obj_in: InstrumentUpdate) -> Instrument:
        if obj_in.symbol:
            db_obj.symbol = obj_in.symbol
        if obj_in.name:
            db_obj.name = obj_in.name
        if obj_in.instrument_type:
            db_obj.instrument_type = obj_in.instrument_type
        if obj_in.isin:
            db_obj.isin = obj_in.isin
        if obj_in.exchange:
            db_obj.exchange = obj_in.exchange

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

instrument = CRUDInstrument()