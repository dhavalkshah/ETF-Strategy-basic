from typing import Any
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.services.portfolio_service import portfolio_service

router = APIRouter()


class HoldingDetail(BaseModel):
    """Details of a single holding."""
    units: float = Field(..., description="Number of units held")
    avg_price: float = Field(..., description="Average purchase price")
    total_invested: float = Field(..., description="Total amount invested")
    instrument_id: str = Field(..., description="Instrument ID")


class PortfolioSummary(BaseModel):
    """Complete portfolio summary."""
    holdings: dict[str, HoldingDetail]
    cash_balance: float = Field(..., description="Cash balance (negative = net invested)")
    total_invested: float = Field(..., description="Total amount invested across all instruments")
    num_instruments: int = Field(..., description="Number of unique instruments held")
    total_units: float = Field(..., description="Total units across all instruments")
    as_of_date: date = Field(..., description="Date of portfolio calculation")


@router.get(
    "/",
    response_model=PortfolioSummary,
    status_code=status.HTTP_200_OK,
    summary="Get Portfolio Summary",
    description="Get complete portfolio summary calculated from transaction history"
)
async def get_portfolio(
    as_of_date: date = Query(None, description="Calculate holdings as of this date (default: today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get your complete portfolio summary.
    
    Portfolio is calculated from your transaction history:
    - BUY/SIP/DIP_BUY transactions increase holdings
    - SELL transactions decrease holdings
    - Average price is calculated based on all purchases
    
    Parameters:
    - **as_of_date**: Optional date to calculate holdings as of (default: today)
    
    Returns:
    - Holdings for each instrument
    - Cash balance
    - Total invested amount
    - Number of instruments
    """
    try:
        summary = portfolio_service.get_portfolio_summary(
            db, 
            current_user,
            as_of_date=as_of_date
        )
        
        # Convert holdings to HoldingDetail objects
        holdings_dict = {}
        for symbol, data in summary.get("holdings", {}).items():
            holdings_dict[symbol] = HoldingDetail(
                units=data["units"],
                avg_price=data["avg_price"],
                total_invested=data["total_invested"],
                instrument_id=data["instrument_id"]
            )
        
        return PortfolioSummary(
            holdings=holdings_dict,
            cash_balance=summary.get("cash_balance", 0.0),
            total_invested=summary.get("total_invested", 0.0),
            num_instruments=summary.get("num_instruments", 0),
            total_units=summary.get("total_units", 0.0),
            as_of_date=summary.get("as_of_date", date.today())
        )
        
    except Exception as e:
        import logging
        logging.error(f"Error fetching portfolio: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching portfolio data"
        )


@router.get(
    "/{instrument_symbol}",
    response_model=HoldingDetail,
    status_code=status.HTTP_200_OK,
    summary="Get Holdings for Specific Instrument",
    description="Get holding details for a specific instrument"
)
async def get_instrument_holding(
    instrument_symbol: str,
    as_of_date: date = Query(None, description="Calculate holdings as of this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get holding details for a specific instrument.
    
    Returns 404 if you don't hold this instrument.
    """
    try:
        holdings = portfolio_service.get_current_holdings(
            db,
            current_user,
            instrument_symbol=instrument_symbol.upper(),
            as_of_date=as_of_date
        )
        
        symbol_upper = instrument_symbol.upper()
        if symbol_upper not in holdings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No holdings found for {instrument_symbol}"
            )
        
        data = holdings[symbol_upper]
        return HoldingDetail(
            units=data["units"],
            avg_price=data["avg_price"],
            total_invested=data["total_invested"],
            instrument_id=data["instrument_id"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching instrument holding: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching holding data"
        )