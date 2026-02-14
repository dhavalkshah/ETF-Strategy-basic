import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import User, Instrument
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service
from app.strategy.models import StrategyInput, StrategyResult
from app.strategy.backtest_engine import run_backtest

logger = logging.getLogger(__name__)

class StrategyService:
    async def run_backtest_strategy(self, db: Session, user: User, strategy_input: StrategyInput) -> StrategyResult:
        # 1. Get historical data for the instrument
        historical_data = await data_service.get_historical_data(
            db,
            strategy_input.symbol,
            strategy_input.instrument_type,
            strategy_input.start_date,
            strategy_input.end_date
        )

        if not historical_data:
            return StrategyResult(
                equity_curve=[],
                transactions=[],
                summary_stats=SummaryStatistics(
                    total_investment=0,
                    final_portfolio_value=0,
                    absolute_return=0,
                    message="No historical data found for the given instrument and date range."
                ),
                message="Backtest failed: No historical data."
            )
        
        # 2. Get historical data for the benchmark if provided
        benchmark_data: Optional[List[HistoricalPrice]] = None
        if strategy_input.benchmark_index:
            benchmark_data = await data_service.get_historical_data(
                db,
                strategy_input.benchmark_index,
                "INDEX", # Assuming benchmark is always an INDEX type for now
                strategy_input.start_date,
                strategy_input.end_date
            )
            if not benchmark_data:
                logger.warning(f"Could not retrieve benchmark data for {strategy_input.benchmark_index}. Backtest will proceed without benchmark.")

        # 3. Run the pure strategy engine
        result = run_backtest(
            historical_data=historical_data,
            strategy_input=strategy_input,
            benchmark_data=benchmark_data
        )

        # TODO: Save backtest_results to DB

        return result

strategy_service = StrategyService()