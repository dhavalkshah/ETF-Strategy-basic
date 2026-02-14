from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# --- Input Models ---
class StrategyInput(BaseModel):
    instrument_type: str # MF or ETF
    symbol: str
    sip_amount: float = Field(default=1000.0, ge=0)
    start_date: date
    end_date: date
    benchmark_index: Optional[str] = None
    dip_multiplier: Optional[float] = None
    carry_over_fraction: float = Field(default=0.5, ge=0, le=1)

# --- Output Models ---
class TransactionRecord(BaseModel):
    date: date
    type: str # BUY, SELL, SIP
    quantity: float
    price_per_unit: float
    amount: float
    cash_balance: float
    units_accumulated: float

class DailyPortfolioValue(BaseModel):
    date: date
    value: float

class SummaryStatistics(BaseModel):
    total_investment: float
    final_portfolio_value: float
    absolute_return: float
    xirr: Optional[float] = None
    benchmark_return: Optional[float] = None
    cagr: Optional[float] = None # Compound Annual Growth Rate

class StrategyResult(BaseModel):
    equity_curve: List[DailyPortfolioValue]
    benchmark_curve: List[DailyPortfolioValue] = Field(default_factory=list)
    transactions: List[TransactionRecord]
    summary_stats: SummaryStatistics
    message: Optional[str] = None # e.g., "Strategy executed successfully"

# --- Advisor Models ---
class AdvisorRecommendation(BaseModel):
    recommended_amount: float # Amount to SIP or dip buy
    reason: str
    portfolio_state_snapshot: Optional[dict] = None # Current holdings, cash, etc.
