import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, Numeric, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.types import BigInteger 
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(email='{self.email}')>"


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    instrument_type = Column(
        Enum('EQUITY', 'ETF', 'MF', 'INDEX', name='instrument_type_enum'),
        nullable=False
    )
    isin = Column(String, index=True, nullable=True)
    exchange = Column(String, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    historical_prices = relationship("HistoricalPrice", back_populates="instrument")
    transactions = relationship("Transaction", back_populates="instrument")
    backtest_results = relationship("BacktestResult", back_populates="instrument")

    def __repr__(self):
        return f"<Instrument(symbol='{self.symbol}', type='{self.instrument_type}')>"


class HistoricalPrice(Base):
    __tablename__ = "historical_prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Numeric(10, 2), nullable=True)
    high = Column(Numeric(10, 2), nullable=True)
    low = Column(Numeric(10, 2), nullable=True)
    close = Column(Numeric(10, 2), nullable=False)
    adjusted_close = Column(Numeric(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    instrument = relationship("Instrument", back_populates="historical_prices")

    __table_args__ = (
        UniqueConstraint('instrument_id', 'date', name='_instrument_date_uc'),
    )

    def __repr__(self):
        return f"<HistoricalPrice(symbol_id='{self.instrument_id}', date='{self.date}', close='{self.close}')>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True)
    backtest_id = Column(UUID(as_uuid=True), ForeignKey("backtest_results.id"), index=True, nullable=True)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), index=True, nullable=False)
    transaction_date = Column(Date, index=True, nullable=False)
    transaction_type = Column(
        Enum('BUY', 'SELL', 'DIVIDEND', 'SIP', 'DIP_BUY', name='transaction_type_enum'),
        nullable=False
    )
    quantity = Column(Numeric(10, 4), nullable=False)
    price_per_unit = Column(Numeric(10, 4), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    fees = Column(Numeric(10, 2), default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    instrument = relationship("Instrument", back_populates="transactions")
    backtest_result = relationship("BacktestResult", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(type='{self.transaction_type}', amount='{self.amount}', date='{self.transaction_date}')>"


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), index=True, nullable=False)
    strategy_name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    parameters = Column(JSONB, nullable=True)
    equity_curve = Column(JSONB, nullable=True)
    benchmark_curve = Column(JSONB, nullable=True)
    xirr = Column(Numeric(10, 4), nullable=True)
    summary_stats = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="backtest_results")
    instrument = relationship("Instrument", back_populates="backtest_results")
    transactions = relationship("Transaction", back_populates="backtest_result")

    def __repr__(self):
        return f"<BacktestResult(user_id='{self.user_id}', strategy='{self.strategy_name}')>"


class SymbolCache(Base):
    __tablename__ = "symbol_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    instrument_type = Column(
        Enum('EQUITY', 'ETF', 'MF', 'INDEX', name='symbol_instrument_type_enum'),
        nullable=False
    )
    source = Column(String, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SymbolCache(symbol='{self.symbol}', type='{self.instrument_type}')>"


# Relationships
User.transactions = relationship("Transaction", back_populates="user")
User.backtest_results = relationship("BacktestResult", back_populates="user")