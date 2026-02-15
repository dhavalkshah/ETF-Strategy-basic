from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.strategy.models import TransactionType


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True
    )
    
    instrument_symbol: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Trading symbol or scheme code"
    )
    transaction_date: date = Field(..., description="Transaction date")
    transaction_type: TransactionType = Field(..., description="Transaction type")
    quantity: float = Field(..., gt=0, description="Quantity (must be positive)")
    price_per_unit: float = Field(..., gt=0, description="Price per unit (must be positive)")
    amount: float = Field(..., description="Transaction amount")
    fees: float = Field(default=0.0, ge=0, description="Transaction fees")
    backtest_id: Optional[UUID] = Field(None, description="Optional backtest ID if from backtest")
    
    @field_validator('instrument_symbol')
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        """Normalize symbol to uppercase."""
        return v.strip().upper()
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float, values) -> float:
        """Validate amount matches quantity * price_per_unit for BUY/SELL."""
        if 'transaction_type' in values.data and 'quantity' in values.data and 'price_per_unit' in values.data:
            expected_amount = values.data['quantity'] * values.data['price_per_unit']
            if values.data['transaction_type'] in [TransactionType.BUY, TransactionType.SELL]:
                # Allow small floating point differences
                if abs(v - expected_amount) > 0.01:
                    raise ValueError(
                        f"Amount {v} does not match quantity * price ({expected_amount:.2f})"
                    )
        return v


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    
    model_config = ConfigDict(str_strip_whitespace=True)
    
    transaction_date: Optional[date] = None
    quantity: Optional[float] = Field(None, gt=0)
    price_per_unit: Optional[float] = Field(None, gt=0)
    amount: Optional[float] = None
    fees: Optional[float] = Field(None, ge=0)


class TransactionOut(BaseModel):
    """Schema for transaction output."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: Optional[UUID]
    backtest_id: Optional[UUID]
    instrument_id: UUID
    transaction_date: date
    transaction_type: str
    quantity: float
    price_per_unit: float
    amount: float
    fees: float
    created_at: date
    
    # Optional nested data
    instrument_symbol: Optional[str] = None
    instrument_name: Optional[str] = None


class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list."""
    
    total: int
    page: int
    page_size: int
    transactions: list[TransactionOut]


class TransactionSummary(BaseModel):
    """Schema for transaction summary statistics."""
    
    total_transactions: int
    total_buy_amount: float
    total_sell_amount: float
    total_fees: float
    net_investment: float
    unique_instruments: int
    date_range: dict[str, Optional[date]]