from typing import List, Optional
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import HistoricalPrice
from app.schemas.instrument import HistoricalPriceCreate, HistoricalPriceBase

class CRUDHistoricalPrice:
    def get(self, db: Session, historical_price_id: UUID) -> Optional[HistoricalPrice]:
        return db.query(HistoricalPrice).filter(HistoricalPrice.id == historical_price_id).first()

    def get_by_instrument_and_date(self, db: Session, instrument_id: UUID, date: date) -> Optional[HistoricalPrice]:
        return db.query(HistoricalPrice).filter(
            HistoricalPrice.instrument_id == instrument_id,
            HistoricalPrice.date == date
        ).first()

    def get_historical_prices_for_instrument(
        self, db: Session, instrument_id: UUID, start_date: date, end_date: date
    ) -> List[HistoricalPrice]:
        return db.query(HistoricalPrice).filter(
            HistoricalPrice.instrument_id == instrument_id,
            HistoricalPrice.date >= start_date,
            HistoricalPrice.date <= end_date
        ).order_by(HistoricalPrice.date).all()

    def create(self, db: Session, obj_in: HistoricalPriceCreate, instrument_id: UUID) -> HistoricalPrice:
        db_obj = HistoricalPrice(
            instrument_id=instrument_id,
            date=obj_in.date,
            open=obj_in.open,
            high=obj_in.high,
            low=obj_in.low,
            close=obj_in.close,
            adjusted_close=obj_in.adjusted_close,
            volume=obj_in.volume
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_multi(self, db: Session, objs_in: List[HistoricalPriceCreate], instrument_id: UUID) -> List[HistoricalPrice]:
        db_objs = []
        for obj_in in objs_in:
            db_obj = HistoricalPrice(
                instrument_id=instrument_id,
                date=obj_in.date,
                open=obj_in.open,
                high=obj_in.high,
                low=obj_in.low,
                close=obj_in.close,
                adjusted_close=obj_in.adjusted_close,
                volume=obj_in.volume
            )
            db_objs.append(db_obj)
        db.add_all(db_objs)
        db.commit()
        for db_obj in db_objs:
            db.refresh(db_obj)
        return db_objs

historical_price = CRUDHistoricalPrice()