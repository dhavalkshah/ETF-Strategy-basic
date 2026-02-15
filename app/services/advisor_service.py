import logging
from datetime import date, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import User, Instrument, HistoricalPrice
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service
from app.services.portfolio_service import portfolio_service
from app.strategy.models import AdvisorRecommendation
from app.strategy.advisor_logic import get_advisor_recommendation

logger = logging.getLogger(__name__)


class AdvisorService:
    """
    Service for generating daily investment recommendations based on technical indicators.
    
    Now uses actual transaction data to calculate holdings instead of hypothetical values.
    """
    
    RSI_PERIOD = 14
    RSI_LOOKBACK_DAYS = 45
    
    async def get_daily_recommendation(
        self,
        db: Session,
        user: User,
        instrument_symbol: str,
        sip_amount: float,
        dip_multiplier: float = 1.0
    ) -> AdvisorRecommendation:
        """
        Generates daily investment recommendation for a specific instrument.
        
        Uses user's actual transaction history to determine current holdings.
        
        Args:
            db: Database session
            user: Current user
            instrument_symbol: Symbol of the instrument to analyze
            sip_amount: Regular SIP amount
            dip_multiplier: Multiplier for dip buying (default 1.0)
            
        Returns:
            AdvisorRecommendation with investment amount and reasoning
        """
        
        # 1. Get instrument details
        db_instrument = instrument_service.get_instrument_by_symbol(db, instrument_symbol)
        if not db_instrument:
            logger.warning(f"Instrument {instrument_symbol} not found in database.")
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"Instrument {instrument_symbol} not found.",
                portfolio_state_snapshot={
                    "current_holdings": {},
                    "cash_balance": 0.0
                },
                signal_type="HOLD"
            )
        
        # 2. Get user's current holdings from transaction history
        try:
            portfolio_summary = portfolio_service.get_portfolio_summary(db, user)
            
            # Extract holdings for this specific instrument
            current_holdings = portfolio_summary.get("holdings", {})
            cash_balance = portfolio_summary.get("cash_balance", 0.0)
            
            # Get units for this specific instrument
            instrument_holdings = current_holdings.get(instrument_symbol.upper(), {})
            current_units = instrument_holdings.get('units', 0.0)
            
            logger.info(
                f"Portfolio for {user.email}: "
                f"{instrument_symbol} units={current_units}, "
                f"cash_balance={cash_balance}"
            )
            
        except Exception as e:
            logger.error(f"Error fetching portfolio data: {e}", exc_info=True)
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason="Error retrieving portfolio data. Please try again.",
                portfolio_state_snapshot={
                    "current_holdings": {},
                    "cash_balance": 0.0
                },
                signal_type="HOLD"
            )
        
        # 3. Fetch historical data for RSI calculation
        current_date = date.today()
        start_date = current_date - timedelta(days=self.RSI_LOOKBACK_DAYS)
        
        try:
            historical_prices = await data_service.get_historical_data(
                db,
                instrument_symbol,
                db_instrument.instrument_type,
                start_date,
                current_date
            )
        except ValueError as e:
            logger.error(f"Invalid instrument type for {instrument_symbol}: {e}")
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"Unsupported instrument type: {db_instrument.instrument_type}",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )
        except Exception as e:
            logger.error(f"Error fetching historical data for {instrument_symbol}: {e}")
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason="Error fetching market data. Please try again later.",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )
        
        if not historical_prices:
            logger.warning(f"No historical data available for {instrument_symbol}.")
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"No historical data available for {instrument_symbol}.",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )
        
        # Ensure historical prices are sorted by date (ascending)
        historical_prices.sort(key=lambda hp: hp.date)
        
        # 4. Validate sufficient data for RSI calculation
        min_required_days = self.RSI_PERIOD + 1
        if len(historical_prices) < min_required_days:
            logger.warning(
                f"Insufficient data for {instrument_symbol}. "
                f"Need {min_required_days} days, got {len(historical_prices)}."
            )
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"Insufficient historical data (need at least {min_required_days} trading days).",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )
        
        # 5. Determine which data to use for analysis
        latest_date = historical_prices[-1].date
        
        if latest_date == current_date:
            # Today's data is available - use data up to yesterday for analysis
            if len(historical_prices) < 2:
                logger.warning(f"Only today's data available for {instrument_symbol}.")
                return AdvisorRecommendation(
                    recommended_amount=0.0,
                    reason="Need at least one previous day's data for analysis.",
                    portfolio_state_snapshot={
                        "current_holdings": current_holdings,
                        "cash_balance": cash_balance
                    },
                    signal_type="HOLD"
                )
            historical_prices_for_analysis = historical_prices[:-1]
        else:
            historical_prices_for_analysis = historical_prices
        
        # Final validation after filtering
        if len(historical_prices_for_analysis) < min_required_days:
            logger.warning(
                f"After filtering, insufficient data for {instrument_symbol}."
            )
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"Insufficient historical data for analysis.",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )
        
        # 6. Call the advisor logic with actual portfolio data
        try:
            # Format current holdings for advisor logic
            holdings_dict = {instrument_symbol.upper(): current_units}
            
            recommendation = get_advisor_recommendation(
                current_holdings=holdings_dict,
                cash_balance=cash_balance,
                historical_prices=historical_prices_for_analysis,
                sip_amount=sip_amount,
                dip_multiplier=dip_multiplier
            )
            
            logger.info(
                f"Generated recommendation for {user.email}, {instrument_symbol}: "
                f"amount={recommendation.recommended_amount}, "
                f"signal={recommendation.signal_type}"
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error in advisor logic for {instrument_symbol}: {e}")
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason="Error calculating recommendation. Please try again later.",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                },
                signal_type="HOLD"
            )


advisor_service = AdvisorService()