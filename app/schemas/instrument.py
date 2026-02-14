from typing import Optional, List
from datetime import datetime
import uuid

from pydantic import BaseModel, Field

class InstrumentBase(BaseModel):
    symbol: str
    name: str
    instrument_type: str # ETF, MF
    isin: Optional[str] = None
    exchange: Optional[str] = None

class InstrumentCreate(InstrumentBase):
    pass

class InstrumentUpdate(InstrumentBase):
    symbol: Optional[str] = None
    name: Optional[str] = None
    instrument_type: Optional[str] = None

class InstrumentInDBBase(InstrumentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    last_fetched_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

class InstrumentOut(InstrumentInDBBase):
    pass

class HistoricalPriceBase(BaseModel):
    date: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    adjusted_close: float
    volume: Optional[int] = None

class HistoricalPriceCreate(HistoricalPriceBase):
    pass

class HistoricalPriceInDBBase(HistoricalPriceBase):
    id: uuid.UUID
    instrument_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class HistoricalPriceOut(HistoricalPriceInDBBase):
    pass

class SymbolCacheBase(BaseModel):
    symbol: str
    name: str
    instrument_type: str # ETF, MF, INDEX
    source: Optional[str] = None

class SymbolCacheCreate(SymbolCacheBase):
    pass

class SymbolCacheInDBBase(SymbolCacheBase):
    id: uuid.UUID
    last_fetched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class SymbolCacheOut(SymbolCacheInDBBase):
    pass