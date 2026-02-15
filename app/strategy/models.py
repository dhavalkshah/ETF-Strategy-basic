from datetime import date
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict


# --- Enums ---
class InstrumentType(str, Enum):
    """Supported instrument types for trading strategies."""
    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    MF = "MF"


class TransactionType(str, Enum):
    """Types of transactions in portfolio."""
    BUY = "BUY"
    SELL = "SELL"
    SIP = "SIP"
    DIP_BUY = "DIP_BUY"


# --- Input Models ---
class StrategyInput(BaseModel):
    """
    Input configuration for running a backtesting strategy.
    
    Attributes:
        instrument_type: Type of instrument (EQUITY, ETF, INDEX, MF)
        symbol: Trading symbol or scheme code
        sip_amount: Regular SIP amount per period
        start_date: Start date for backtest
        end_date: End date for backtest
        benchmark_index: Optional benchmark index symbol for comparison
        dip_multiplier: Optional multiplier for dip buying (e.g., 2.0 means buy 2x on dips)
        carry_over_fraction: Fraction of unused cash to carry forward (0.0-1.0)
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        use_enum_values=True
    )
    
    instrument_type: InstrumentType
    symbol: str = Field(..., min_length=1, max_length=50, description="Trading symbol or scheme code")
    sip_amount: float = Field(default=1000.0, gt=0, description="Regular SIP amount (must be positive)")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    benchmark_index: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Benchmark index symbol for comparison"
    )
    dip_multiplier: Optional[float] = Field(
        None,
        gt=0,
        le=10,
        description="Multiplier for dip buying (1.0-10.0, e.g., 2.0 = buy 2x on dips)"
    )
    carry_over_fraction: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Fraction of unused cash to carry forward (0.0-1.0)"
    )
    
    @field_validator('symbol', 'benchmark_index')
    @classmethod
    def normalize_symbol(cls, v: Optional[str]) -> Optional[str]:
        """Normalize symbols to uppercase and strip whitespace."""
        if v is None:
            return v
        return v.strip().upper()
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: date, values) -> date:
        """Ensure end_date is after start_date."""
        # In Pydantic v2, we need to access previous values differently
        if 'start_date' in values.data and v <= values.data['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


# --- Output Models ---
class TransactionRecord(BaseModel):
    """
    Record of a single transaction in the portfolio.
    
    Attributes:
        date: Transaction date
        type: Transaction type (BUY, SELL, SIP, DIP_BUY)
        quantity: Number of units transacted
        price_per_unit: Price per unit at transaction
        amount: Total transaction amount
        cash_balance: Cash balance after transaction
        units_accumulated: Total units held after transaction
    """
    
    date: date
    type: TransactionType
    quantity: float = Field(..., ge=0, description="Quantity must be non-negative")
    price_per_unit: float = Field(..., gt=0, description="Price must be positive")
    amount: float = Field(..., description="Transaction amount (can be negative for sells)")
    cash_balance: float = Field(..., ge=0, description="Cash balance after transaction")
    units_accumulated: float = Field(..., ge=0, description="Total units held after transaction")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "type": "SIP",
                "quantity": 10.5,
                "price_per_unit": 95.24,
                "amount": 1000.0,
                "cash_balance": 5000.0,
                "units_accumulated": 150.5
            }
        }
    )


class DailyPortfolioValue(BaseModel):
    """
    Daily snapshot of portfolio value.
    
    Attributes:
        date: Portfolio value date
        value: Total portfolio value on this date
    """
    
    date: date
    value: float = Field(..., ge=0, description="Portfolio value must be non-negative")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "value": 125000.50
            }
        }
    )


class SummaryStatistics(BaseModel):
    """
    Summary statistics for strategy performance.
    
    Attributes:
        total_investment: Total amount invested
        final_portfolio_value: Final portfolio value at end date
        absolute_return: Absolute return amount
        absolute_return_pct: Absolute return percentage
        xirr: XIRR (Extended Internal Rate of Return) in percentage
        benchmark_return: Benchmark return percentage (if benchmark provided)
        cagr: Compound Annual Growth Rate in percentage
        max_drawdown: Maximum drawdown percentage
        message: Additional information or status message
    """
    
    total_investment: float = Field(..., ge=0, description="Total invested amount")
    final_portfolio_value: float = Field(..., ge=0, description="Final portfolio value")
    absolute_return: float = Field(..., description="Absolute return amount")
    absolute_return_pct: Optional[float] = Field(None, description="Absolute return percentage")
    xirr: Optional[float] = Field(None, description="XIRR percentage")
    benchmark_return: Optional[float] = Field(None, description="Benchmark return percentage")
    cagr: Optional[float] = Field(None, description="CAGR percentage")
    max_drawdown: Optional[float] = Field(None, le=0, description="Maximum drawdown percentage (negative)")
    message: Optional[str] = Field(None, max_length=500, description="Status or info message")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_investment": 100000.0,
                "final_portfolio_value": 125000.0,
                "absolute_return": 25000.0,
                "absolute_return_pct": 25.0,
                "xirr": 22.5,
                "benchmark_return": 18.0,
                "cagr": 23.1,
                "max_drawdown": -12.5,
                "message": "Strategy executed successfully"
            }
        }
    )


class StrategyResult(BaseModel):
    """
    Complete result of a strategy backtest.
    
    Attributes:
        equity_curve: Daily portfolio values over backtest period
        benchmark_curve: Daily benchmark values (if benchmark provided)
        transactions: List of all transactions executed
        summary_stats: Summary statistics of strategy performance
        message: Overall status or info message
    """
    
    equity_curve: List[DailyPortfolioValue] = Field(
        ...,
        min_length=0,
        description="Daily portfolio values"
    )
    benchmark_curve: List[DailyPortfolioValue] = Field(
        default_factory=list,
        description="Daily benchmark values"
    )
    transactions: List[TransactionRecord] = Field(
        ...,
        min_length=0,
        description="Transaction history"
    )
    summary_stats: SummaryStatistics
    message: Optional[str] = Field(
        None,
        max_length=500,
        description="Overall status message"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "equity_curve": [
                    {"date": "2024-01-01", "value": 100000.0},
                    {"date": "2024-01-02", "value": 101500.0}
                ],
                "benchmark_curve": [],
                "transactions": [],
                "summary_stats": {
                    "total_investment": 100000.0,
                    "final_portfolio_value": 125000.0,
                    "absolute_return": 25000.0
                },
                "message": "Backtest completed successfully"
            }
        }
    )


# --- Advisor Models ---
class AdvisorRecommendation(BaseModel):
    """
    Daily investment recommendation from the advisor.
    
    Attributes:
        recommended_amount: Amount to invest (SIP or dip buy)
        reason: Explanation for the recommendation
        portfolio_state_snapshot: Current portfolio state (holdings, cash, etc.)
        rsi_value: RSI value used for recommendation (if applicable)
        signal_type: Type of signal (SIP, DIP_BUY, HOLD)
    """
    
    recommended_amount: float = Field(
        ...,
        ge=0,
        description="Recommended investment amount (non-negative)"
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Explanation for recommendation"
    )
    portfolio_state_snapshot: Optional[dict] = Field(
        None,
        description="Current portfolio state"
    )
    rsi_value: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="RSI value (0-100)"
    )
    signal_type: Optional[str] = Field(
        None,
        description="Signal type: SIP, DIP_BUY, HOLD"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommended_amount": 2000.0,
                "reason": "RSI indicates oversold condition (RSI: 28.5). Recommending dip buy at 2x SIP.",
                "portfolio_state_snapshot": {
                    "current_holdings": {"NIFTYBEES": 150.5},
                    "cash_balance": 10000.0
                },
                "rsi_value": 28.5,
                "signal_type": "DIP_BUY"
            }
        }
    )