import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.db.models import Transaction, Instrument, User
from app.schemas.transaction import TransactionCreate, TransactionUpdate

logger = logging.getLogger(__name__)


class CRUDTransaction:
    """CRUD operations for Transaction model."""
    
    def create(
        self,
        db: Session,
        *,
        obj_in: TransactionCreate,
        user_id: UUID,
        instrument_id: UUID
    ) -> Transaction:
        """
        Create a new transaction.
        
        Args:
            db: Database session
            obj_in: Transaction creation data
            user_id: User ID
            instrument_id: Instrument ID
            
        Returns:
            Created Transaction object
        """
        db_obj = Transaction(
            user_id=user_id,
            instrument_id=instrument_id,
            transaction_date=obj_in.transaction_date,
            transaction_type=obj_in.transaction_type,
            quantity=obj_in.quantity,
            price_per_unit=obj_in.price_per_unit,
            amount=obj_in.amount,
            fees=obj_in.fees,
            backtest_id=obj_in.backtest_id
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, transaction_id: UUID) -> Optional[Transaction]:
        """Get a transaction by ID."""
        return db.query(Transaction).filter(Transaction.id == transaction_id).first()
    
    def get_with_instrument(self, db: Session, transaction_id: UUID) -> Optional[Transaction]:
        """Get a transaction with instrument details loaded."""
        return (
            db.query(Transaction)
            .options(joinedload(Transaction.instrument))
            .filter(Transaction.id == transaction_id)
            .first()
        )
    
    def get_multi_by_user(
        self,
        db: Session,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        instrument_id: Optional[UUID] = None,
        transaction_type: Optional[str] = None
    ) -> tuple[List[Transaction], int]:
        """
        Get multiple transactions for a user with filters.
        
        Returns:
            Tuple of (transactions list, total count)
        """
        query = (
            db.query(Transaction)
            .options(joinedload(Transaction.instrument))
            .filter(Transaction.user_id == user_id)
        )
        
        # Apply filters
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)
        if instrument_id:
            query = query.filter(Transaction.instrument_id == instrument_id)
        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        transactions = (
            query
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        return transactions, total
    
    def get_multi_by_backtest(
        self,
        db: Session,
        backtest_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        """Get all transactions for a specific backtest."""
        return (
            db.query(Transaction)
            .options(joinedload(Transaction.instrument))
            .filter(Transaction.backtest_id == backtest_id)
            .order_by(Transaction.transaction_date.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def update(
        self,
        db: Session,
        *,
        db_obj: Transaction,
        obj_in: TransactionUpdate
    ) -> Transaction:
        """Update a transaction."""
        update_data = obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, transaction_id: UUID) -> bool:
        """Delete a transaction."""
        obj = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if obj:
            db.delete(obj)
            db.commit()
            return True
        return False
    
    def get_summary(
        self,
        db: Session,
        user_id: UUID,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """
        Get transaction summary statistics for a user.
        
        Returns:
            Dictionary with summary statistics
        """
        query = db.query(Transaction).filter(Transaction.user_id == user_id)
        
        if start_date:
            query = query.filter(Transaction.transaction_date >= start_date)
        if end_date:
            query = query.filter(Transaction.transaction_date <= end_date)
        
        # Total transactions
        total_transactions = query.count()
        
        # Sum by transaction type
        buy_sum = (
            query.filter(Transaction.transaction_type.in_(['BUY', 'SIP']))
            .with_entities(func.sum(Transaction.amount))
            .scalar() or 0.0
        )
        
        sell_sum = (
            query.filter(Transaction.transaction_type == 'SELL')
            .with_entities(func.sum(Transaction.amount))
            .scalar() or 0.0
        )
        
        total_fees = (
            query.with_entities(func.sum(Transaction.fees))
            .scalar() or 0.0
        )
        
        # Unique instruments
        unique_instruments = (
            query.with_entities(func.count(func.distinct(Transaction.instrument_id)))
            .scalar() or 0
        )
        
        # Date range
        date_range_query = query.with_entities(
            func.min(Transaction.transaction_date),
            func.max(Transaction.transaction_date)
        ).first()
        
        return {
            "total_transactions": total_transactions,
            "total_buy_amount": float(buy_sum),
            "total_sell_amount": float(sell_sum),
            "total_fees": float(total_fees),
            "net_investment": float(buy_sum - sell_sum),
            "unique_instruments": unique_instruments,
            "date_range": {
                "start": date_range_query[0] if date_range_query else None,
                "end": date_range_query[1] if date_range_query else None
            }
        }


transaction = CRUDTransaction()