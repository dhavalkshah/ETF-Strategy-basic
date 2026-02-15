import logging
import time
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import User
from app.services.data_service import data_service
from app.services.instrument_service import instrument_service
from app.strategy.models import StrategyInput, StrategyResult, SummaryStatistics
from app.strategy.backtest_engine import run_backtest

logger = logging.getLogger(__name__)


class StrategyService:
    """Service for running backtesting strategies on historical market data."""
    
    MIN_BACKTEST_DAYS = 30
    
    async def run_backtest_strategy(
        self,
        db: Session,
        user: User,
        strategy_input: StrategyInput
    ) -> StrategyResult:
        """Runs a backtest strategy for a given instrument over a specified date range."""
        
        overall_start = time.time()
        logger.info("=" * 100)
        logger.info(f"STRATEGY SERVICE START")
        logger.info(f"User: {user.email}")
        logger.info(f"Symbol: {strategy_input.symbol}")
        logger.info(f"Type: {strategy_input.instrument_type}")
        logger.info(f"Date Range: {strategy_input.start_date} to {strategy_input.end_date}")
        logger.info(f"Benchmark: {strategy_input.benchmark_index}")
        logger.info("=" * 100)
        
        # 1. Validate strategy input
        step_start = time.time()
        logger.info("STEP 1: Validating inputs...")
        
        if strategy_input.start_date >= strategy_input.end_date:
            logger.warning("Invalid date range")
            return self._create_error_result("Invalid date range: start_date must be before end_date.")
        
        date_range_days = (strategy_input.end_date - strategy_input.start_date).days
        if date_range_days < self.MIN_BACKTEST_DAYS:
            logger.warning(f"Date range too short: {date_range_days} days")
            return self._create_error_result(
                f"Date range too short. Minimum {self.MIN_BACKTEST_DAYS} days recommended."
            )
        
        # Validate benchmark
        benchmark_index = strategy_input.benchmark_index
        if benchmark_index:
            benchmark_index = benchmark_index.strip().upper()
            if benchmark_index in ["STRING", "NONE", "", "NULL"]:
                logger.info(f"Ignoring placeholder benchmark: {benchmark_index}")
                benchmark_index = None
        
        logger.info(f"STEP 1 DONE in {time.time() - step_start:.2f}s")
        logger.info(f"  Date range: {date_range_days} days")
        logger.info(f"  Benchmark: {benchmark_index or 'None'}")
        
        # 2. Fetch main instrument data
        step_start = time.time()
        logger.info(f"STEP 2: Fetching historical data for {strategy_input.symbol}...")
        
        try:
            historical_data = await data_service.get_historical_data(
                db,
                strategy_input.symbol,
                strategy_input.instrument_type,
                strategy_input.start_date,
                strategy_input.end_date
            )
            
            fetch_time = time.time() - step_start
            logger.info(f"STEP 2 DONE in {fetch_time:.2f}s")
            
            if not historical_data:
                logger.warning("No historical data returned")
                return self._create_error_result(
                    f"No historical data found for {strategy_input.symbol} in the specified date range."
                )
            
            logger.info(f"  Retrieved {len(historical_data)} data points")
            logger.info(f"  Date range: {historical_data[0].date} to {historical_data[-1].date}")
            
            if len(historical_data) < 10:
                logger.warning(f"Insufficient data: {len(historical_data)} points")
                return self._create_error_result(
                    f"Insufficient historical data ({len(historical_data)} trading days)."
                )
            
        except ValueError as e:
            logger.error(f"ValueError fetching data: {e}")
            return self._create_error_result(f"Unsupported instrument type: {strategy_input.instrument_type}")
        except Exception as e:
            logger.error(f"Exception fetching data: {e}", exc_info=True)
            return self._create_error_result("Error fetching market data. Please try again later.")
        
        # 3. Fetch benchmark data if needed
        benchmark_data = None
        if benchmark_index:
            step_start = time.time()
            logger.info(f"STEP 3: Fetching benchmark data for {benchmark_index}...")
            
            try:
                benchmark_data = await data_service.get_historical_data(
                    db,
                    benchmark_index,
                    "INDEX",
                    strategy_input.start_date,
                    strategy_input.end_date
                )
                
                fetch_time = time.time() - step_start
                logger.info(f"STEP 3 DONE in {fetch_time:.2f}s")
                
                if not benchmark_data:
                    logger.warning(f"No benchmark data found for {benchmark_index}")
                elif len(benchmark_data) < len(historical_data) * 0.8:
                    logger.warning(
                        f"Benchmark incomplete: {len(benchmark_data)} vs {len(historical_data)} points"
                    )
                else:
                    logger.info(f"  Retrieved {len(benchmark_data)} benchmark points")
                    
            except Exception as e:
                logger.warning(f"Error fetching benchmark: {e}")
                benchmark_data = None
        else:
            logger.info("STEP 3: SKIPPED (no benchmark)")
        
        # 4. Run backtest
        step_start = time.time()
        logger.info(f"STEP 4: Running backtest engine...")
        
        try:
            result = run_backtest(
                historical_data=historical_data,
                strategy_input=strategy_input,
                benchmark_data=benchmark_data
            )
            
            backtest_time = time.time() - step_start
            logger.info(f"STEP 4 DONE in {backtest_time:.2f}s")
            
            total_time = time.time() - overall_start
            logger.info("=" * 100)
            logger.info(f"STRATEGY SERVICE COMPLETE in {total_time:.2f}s")
            logger.info(f"  Data fetch: Step 2 + Step 3")
            logger.info(f"  Backtest engine: {backtest_time:.2f}s")
            logger.info(f"  Total: {total_time:.2f}s")
            logger.info("=" * 100)
            
            return result
            
        except Exception as e:
            logger.error(f"Exception in backtest engine: {e}", exc_info=True)
            return self._create_error_result("Error running backtest calculation.")
    
    def _create_error_result(self, message: str) -> StrategyResult:
        """Creates a standardized error result for failed backtests."""
        logger.error(f"Creating error result: {message}")
        return StrategyResult(
            equity_curve=[],
            transactions=[],
            summary_stats=SummaryStatistics(
                total_investment=0.0,
                final_portfolio_value=0.0,
                absolute_return=0.0,
                absolute_return_pct=0.0,
                message=message
            ),
            message=f"Backtest failed: {message}"
        )


strategy_service = StrategyService()