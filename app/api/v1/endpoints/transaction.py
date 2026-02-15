from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionOut,
    TransactionListResponse,
    TransactionSummary
)
from app.services.transaction_service import transaction_service
from app.strategy.models import TransactionType

router = APIRouter()


@router.post("/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Create a new transaction.
    
    Records a buy, sell, SIP, or dividend transaction for the current user.
    The instrument must exist in the database before creating the transaction.
    """
    # Validate transaction type
    valid_types = [t.value for t in TransactionType]
    if transaction_in.transaction_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transaction_type. Must be one of: {', '.join(valid_types)}"
        )
    
    # Validate date is not in the future
    if transaction_in.transaction_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction date cannot be in the future"
        )
    
    # Create transaction
    transaction = transaction_service.create_transaction(db, current_user, transaction_in)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create transaction. Ensure instrument '{transaction_in.instrument_symbol}' exists."
        )
    
    return transaction


@router.get("/", response_model=TransactionListResponse, status_code=status.HTTP_200_OK)
async def get_transactions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    instrument_symbol: Optional[str] = Query(None, description="Filter by instrument symbol"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get paginated list of transactions for the current user.
    
    Supports filtering by:
    - Date range (start_date, end_date)
    - Instrument symbol
    - Transaction type (BUY, SELL, SIP, DIVIDEND, DIP_BUY)
    """
    # Validate transaction type if provided
    if transaction_type:
        valid_types = [t.value for t in TransactionType]
        if transaction_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction_type. Must be one of: {', '.join(valid_types)}"
            )
    
    # Validate date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date"
        )
    
    # Get transactions
    transactions, total = transaction_service.get_transactions(
        db,
        current_user,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        instrument_symbol=instrument_symbol,
        transaction_type=transaction_type
    )
    
    return TransactionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        transactions=transactions
    )


@router.get("/summary", response_model=TransactionSummary, status_code=status.HTTP_200_OK)
async def get_transaction_summary(
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get transaction summary statistics for the current user.
    
    Returns:
    - Total transactions count
    - Total buy/sell amounts
    - Total fees paid
    - Net investment
    - Number of unique instruments
    - Date range of transactions
    """
    # Validate date range
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date"
        )
    
    summary = transaction_service.get_summary(
        db,
        current_user,
        start_date=start_date,
        end_date=end_date
    )
    
    return summary


@router.get("/{transaction_id}", response_model=TransactionOut, status_code=status.HTTP_200_OK)
async def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get a specific transaction by ID.
    
    Returns 404 if transaction doesn't exist or doesn't belong to the current user.
    """
    transaction = transaction_service.get_transaction(db, current_user, transaction_id)
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return transaction


@router.put("/{transaction_id}", response_model=TransactionOut, status_code=status.HTTP_200_OK)
async def update_transaction(
    transaction_id: UUID,
    transaction_update: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Update a transaction.
    
    Can update: transaction_date, quantity, price_per_unit, amount, fees
    Cannot update: transaction_type, instrument
    """
    # Validate date is not in the future if provided
    if transaction_update.transaction_date and transaction_update.transaction_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction date cannot be in the future"
        )
    
    transaction = transaction_service.update_transaction(
        db,
        current_user,
        transaction_id,
        transaction_update
    )
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found or update failed"
        )
    
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> None:
    """
    Delete a transaction.
    
    Returns 404 if transaction doesn't exist or doesn't belong to the current user.
    """
    success = transaction_service.delete_transaction(db, current_user, transaction_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    return None