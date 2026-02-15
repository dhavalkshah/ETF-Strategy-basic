import logging
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud.transaction import transaction as crud_transaction
from app.crud.instrument import instrument as crud_instrument
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionOut,
    TransactionSummary
)
from app.db.models import Transaction, User

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing user transactions."""
    
    def create_transaction(
        self,
        db: Session,
        user: User,
        transaction_in: TransactionCreate
    ) -> Optional[TransactionOut]:
        """
        Create a new transaction for a user.
        
        Args:
            db: Database session
            user: Current user
            transaction_in: Transaction creation data
            
        Returns:
            TransactionOut if successful, None on error
        """
        try:
            # Get or create instrument
            instrument = crud_instrument.get_by_symbol(db, transaction_in.instrument_symbol)
            
            if not instrument:
                logger.error(f"Instrument {transaction_in.instrument_symbol} not found")
                return None
            
            # Create transaction
            transaction = crud_transaction.create(
                db,
                obj_in=transaction_in,
                user_id=user.id,
                instrument_id=instrument.id
            )
            
            logger.info(
                f"Created transaction: user={user.email}, "
                f"symbol={transaction_in.instrument_symbol}, "
                f"type={transaction_in.transaction_type}, "
                f"amount={transaction_in.amount}"
            )
            
            # Convert to output schema
            return self._to_output_schema(transaction)
            
        except Exception as e:
            logger.error(f"Error creating transaction: {e}", exc_info=True)
            return None
    
    def get_transaction(
        self,
        db: Session,
        user: User,
        transaction_id: UUID
    ) -> Optional[TransactionOut]:
        """
        Get a specific transaction for a user.
        
        Args:
            db: Database session
            user: Current user
            transaction_id: Transaction ID
            
        Returns:
            TransactionOut if found and belongs to user, None otherwise
        """
        try:
            transaction = crud_transaction.get_with_instrument(db, transaction_id)
            
            if not transaction or transaction.user_id != user.id:
                logger.warning(
                    f"Transaction {transaction_id} not found or unauthorized for user {user.email}"
                )
                return None
            
            return self._to_output_schema(transaction)
            
        except Exception as e:
            logger.error(f"Error fetching transaction: {e}", exc_info=True)
            return None
    
    def get_transactions(
        self,
        db: Session,
        user: User,
        *,
        page: int = 1,
        page_size: int = 50,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        instrument_symbol: Optional[str] = None,
        transaction_type: Optional[str] = None
    ) -> tuple[List[TransactionOut], int]:
        """
        Get transactions for a user with pagination and filters.
        
        Args:
            db: Database session
            user: Current user
            page: Page number (1-indexed)
            page_size: Items per page
            start_date: Filter by start date
            end_date: Filter by end date
            instrument_symbol: Filter by instrument symbol
            transaction_type: Filter by transaction type
            
        Returns:
            Tuple of (transaction list, total count)
        """
        try:
            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), 100)  # Max 100 per page
            skip = (page - 1) * page_size
            
            # Get instrument_id if symbol provided
            instrument_id = None
            if instrument_symbol:
                instrument = crud_instrument.get_by_symbol(db, instrument_symbol.upper())
                if instrument:
                    instrument_id = instrument.id
                else:
                    logger.warning(f"Instrument {instrument_symbol} not found for filter")
                    return [], 0
            
            # Fetch transactions
            transactions, total = crud_transaction.get_multi_by_user(
                db,
                user.id,
                skip=skip,
                limit=page_size,
                start_date=start_date,
                end_date=end_date,
                instrument_id=instrument_id,
                transaction_type=transaction_type
            )
            
            # Convert to output schemas
            transaction_outs = [self._to_output_schema(t) for t in transactions]
            
            logger.info(
                f"Retrieved {len(transaction_outs)} transactions for user {user.email} "
                f"(page {page}, total {total})"
            )
            
            return transaction_outs, total
            
        except Exception as e:
            logger.error(f"Error fetching transactions: {e}", exc_info=True)
            return [], 0
    
    def update_transaction(
        self,
        db: Session,
        user: User,
        transaction_id: UUID,
        transaction_update: TransactionUpdate
    ) -> Optional[TransactionOut]:
        """
        Update a transaction.
        
        Args:
            db: Database session
            user: Current user
            transaction_id: Transaction ID
            transaction_update: Update data
            
        Returns:
            Updated TransactionOut if successful, None otherwise
        """
        try:
            # Get transaction
            transaction = crud_transaction.get(db, transaction_id)
            
            if not transaction or transaction.user_id != user.id:
                logger.warning(
                    f"Transaction {transaction_id} not found or unauthorized for user {user.email}"
                )
                return None
            
            # Update
            updated_transaction = crud_transaction.update(
                db,
                db_obj=transaction,
                obj_in=transaction_update
            )
            
            logger.info(f"Updated transaction {transaction_id} for user {user.email}")
            
            # Reload with instrument
            updated_transaction = crud_transaction.get_with_instrument(db, transaction_id)
            return self._to_output_schema(updated_transaction)
            
        except Exception as e:
            logger.error(f"Error updating transaction: {e}", exc_info=True)
            return None
    
    def delete_transaction(
        self,
        db: Session,
        user: User,
        transaction_id: UUID
    ) -> bool:
        """
        Delete a transaction.
        
        Args:
            db: Database session
            user: Current user
            transaction_id: Transaction ID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            # Get transaction
            transaction = crud_transaction.get(db, transaction_id)
            
            if not transaction or transaction.user_id != user.id:
                logger.warning(
                    f"Transaction {transaction_id} not found or unauthorized for user {user.email}"
                )
                return False
            
            # Delete
            success = crud_transaction.delete(db, transaction_id)
            
            if success:
                logger.info(f"Deleted transaction {transaction_id} for user {user.email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting transaction: {e}", exc_info=True)
            return False
    
    def get_summary(
        self,
        db: Session,
        user: User,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> TransactionSummary:
        """
        Get transaction summary statistics for a user.
        
        Args:
            db: Database session
            user: Current user
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            TransactionSummary with statistics
        """
        try:
            summary_data = crud_transaction.get_summary(
                db,
                user.id,
                start_date=start_date,
                end_date=end_date
            )
            
            return TransactionSummary(**summary_data)
            
        except Exception as e:
            logger.error(f"Error getting transaction summary: {e}", exc_info=True)
            return TransactionSummary(
                total_transactions=0,
                total_buy_amount=0.0,
                total_sell_amount=0.0,
                total_fees=0.0,
                net_investment=0.0,
                unique_instruments=0,
                date_range={"start": None, "end": None}
            )
    
    def _to_output_schema(self, transaction: Transaction) -> TransactionOut:
        """
        Convert Transaction model to TransactionOut schema.
        
        Args:
            transaction: Transaction model instance
            
        Returns:
            TransactionOut schema
        """
        out_data = {
            "id": transaction.id,
            "user_id": transaction.user_id,
            "backtest_id": transaction.backtest_id,
            "instrument_id": transaction.instrument_id,
            "transaction_date": transaction.transaction_date,
            "transaction_type": transaction.transaction_type,
            "quantity": float(transaction.quantity),
            "price_per_unit": float(transaction.price_per_unit),
            "amount": float(transaction.amount),
            "fees": float(transaction.fees),
            "created_at": transaction.created_at.date()
        }
        
        # Add instrument info if loaded
        if hasattr(transaction, 'instrument') and transaction.instrument:
            out_data["instrument_symbol"] = transaction.instrument.symbol
            out_data["instrument_name"] = transaction.instrument.name
        
        return TransactionOut(**out_data)


transaction_service = TransactionService()