import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from app.db.models import User, Instrument, HistoricalPrice
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service
from app.strategy.models import AdvisorRecommendation
from app.strategy.advisor_logic import get_advisor_recommendation
from app.crud.historical_price import historical_price as crud_historical_price

logger = logging.getLogger(__name__)

class AdvisorService:
    async def get_daily_recommendation(
        self,
        db: Session,
        user: User,
        instrument_symbol: str,
        current_holdings: Dict[str, float], # {instrument_symbol: units}
        cash_balance: float,
        sip_amount: float,
        dip_multiplier: float = 1.0
    ) -> AdvisorRecommendation:
        
        # 1. Get instrument details
        db_instrument = instrument_service.get_instrument_by_symbol(db, instrument_symbol)
        if not db_instrument:
            return AdvisorRecommendation(
                recommended_amount=0.0,
                reason=f"Instrument {instrument_symbol} not found.",
                portfolio_state_snapshot={
                    "current_holdings": current_holdings,
                    "cash_balance": cash_balance
                }
            )

                # 2. Get historical data for RSI calculation (last 30-40 days for 14-period RSI)
                current_processing_date = date.today()
                # For RSI (14 period), we need at least 14 days of data. Fetching more for robustness.
                # Let's fetch enough data to calculate RSI for the `current_processing_date`'s *previous day*.
                # We need `rsi_period` (14) + 1 day of delta + a few buffer days.
                rsi_lookback_days = 30 # Fetch roughly a month of data
                start_date_for_rsi = current_processing_date - timedelta(days=rsi_lookback_days) 
                
                # This will fetch historical prices up to (and including) current_processing_date
                historical_prices = await data_service.get_historical_data(
                    db,
                    instrument_symbol,
                    db_instrument.instrument_type,
                    start_date_for_rsi,
                    current_processing_date
                )
        
                if not historical_prices:
                    return AdvisorRecommendation(
                        recommended_amount=0.0,
                        reason=f"Not enough historical data to generate recommendation for {instrument_symbol}.",
                        portfolio_state_snapshot={
                            "current_holdings": current_holdings,
                            "cash_balance": cash_balance
                        }
                    )
        
                # Ensure historical prices are sorted by date
                historical_prices.sort(key=lambda hp: hp.date)
                
                # The last available price in the fetched data should ideally be for the day before `current_processing_date`
                # or `current_processing_date` itself if data for today is available.
                last_available_historical_data: Optional[HistoricalPrice] = None
                if historical_prices[-1].date == current_processing_date:
                    # If today's data is available, use yesterday's for analysis
                    if len(historical_prices) >= 2:
                        last_available_historical_data = historical_prices[-2]
                        # Filter historical_prices to exclude today's data for RSI calculation to represent 'yesterday's close' context
                        historical_prices_for_analysis = historical_prices[:-1] 
                    else:
                        return AdvisorRecommendation(
                            recommended_amount=0.0,
                            reason=f"Not enough historical data (at least yesterday's close) for {instrument_symbol}.",
                            portfolio_state_snapshot={
                                "current_holdings": current_holdings,
                                "cash_balance": cash_balance
                            }
                        )
                else: # The latest data is from a past day
                    last_available_historical_data = historical_prices[-1]
                    historical_prices_for_analysis = historical_prices # Use all fetched data for RSI
        
                if not last_available_historical_data:
                    return AdvisorRecommendation(
                        recommended_amount=0.0,
                        reason=f"Not enough historical data (at least yesterday's close) for {instrument_symbol}.",
                        portfolio_state_snapshot={
                                "current_holdings": current_holdings,
                                "cash_balance": cash_balance
                        }
                    )
        
                # 3. Call the pure advisor logic
                recommendation = get_advisor_recommendation(
                    current_holdings=current_holdings,
                    cash_balance=cash_balance,
                    historical_prices=historical_prices_for_analysis, # Pass the list for RSI calculation
                    sip_amount=sip_amount,
                    dip_multiplier=dip_multiplier
                )
        return recommendation

advisor_service = AdvisorService()