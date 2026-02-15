from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_active_user
from app.db.models import User
from app.strategy.models import AdvisorRecommendation
from app.services.advisor_service import advisor_service

router = APIRouter()


@router.get(
    "/recommendation/{instrument_symbol}",
    response_model=AdvisorRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Get Investment Recommendation",
    description="""
    Get AI-powered investment recommendation for a specific instrument.
    
    The recommendation is based on:
    - Your actual transaction history and current holdings
    - Technical analysis (RSI, Moving Averages)
    - Market conditions
    
    Returns recommended investment amount and reasoning.
    """
)
async def get_recommendation(
    instrument_symbol: str,
    sip_amount: float = Query(
        1000.0,
        gt=0,
        description="Regular SIP amount in ₹"
    ),
    dip_multiplier: float = Query(
        1.5,
        gt=0,
        le=10,
        description="Multiplier for dip buying (1.0-10.0)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get daily investment recommendation for a specific instrument.
    
    This endpoint analyzes your current portfolio (from transaction history)
    and market conditions to provide personalized investment advice.
    
    Parameters:
    - **instrument_symbol**: Trading symbol (e.g., NIFTYBEES, RELIANCE)
    - **sip_amount**: Your regular SIP amount (default: ₹1000)
    - **dip_multiplier**: How much to invest during dips (default: 1.5x)
    
    Returns:
    - Recommended investment amount
    - Detailed reasoning
    - Current portfolio snapshot
    - RSI value and signal type
    """
    
    # Validate inputs
    if not instrument_symbol or not instrument_symbol.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Instrument symbol is required"
        )
    
    if sip_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SIP amount must be positive"
        )
    
    if dip_multiplier <= 0 or dip_multiplier > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dip multiplier must be between 0 and 10"
        )
    
    # Get recommendation
    recommendation = await advisor_service.get_daily_recommendation(
        db=db,
        user=current_user,
        instrument_symbol=instrument_symbol.strip().upper(),
        sip_amount=sip_amount,
        dip_multiplier=dip_multiplier
    )
    
    return recommendation


@router.get(
    "/portfolio-recommendations",
    response_model=list[AdvisorRecommendation],
    status_code=status.HTTP_200_OK,
    summary="Get Recommendations for All Holdings",
    description="Get investment recommendations for all instruments in your portfolio"
)
async def get_portfolio_recommendations(
    sip_amount: float = Query(1000.0, gt=0, description="Regular SIP amount in ₹"),
    dip_multiplier: float = Query(1.5, gt=0, le=10, description="Multiplier for dip buying"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get investment recommendations for all instruments in your portfolio.
    
    Returns a list of recommendations, one for each instrument you hold.
    """
    from app.services.portfolio_service import portfolio_service
    
    # Get user's portfolio
    portfolio_summary = portfolio_service.get_portfolio_summary(db, current_user)
    holdings = portfolio_summary.get("holdings", {})
    
    if not holdings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No holdings found. Please add transactions first."
        )
    
    # Get recommendations for each instrument
    recommendations = []
    for symbol in holdings.keys():
        try:
            recommendation = await advisor_service.get_daily_recommendation(
                db=db,
                user=current_user,
                instrument_symbol=symbol,
                sip_amount=sip_amount,
                dip_multiplier=dip_multiplier
            )
            recommendations.append(recommendation)
        except Exception as e:
            # Log error but continue with other instruments
            import logging
            logging.error(f"Error getting recommendation for {symbol}: {e}")
            continue
    
    if not recommendations:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations for portfolio"
        )
    
    return recommendations