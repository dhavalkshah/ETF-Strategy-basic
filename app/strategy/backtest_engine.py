import logging
import time
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np

from app.strategy.calculations import calculate_rsi, calculate_ma, calculate_xirr, calculate_cagr, calculate_max_drawdown
from app.strategy.models import (
    StrategyInput,
    StrategyResult,
    DailyPortfolioValue,
    TransactionRecord,
    SummaryStatistics,
    TransactionType
)
from app.db.models import HistoricalPrice

logger = logging.getLogger(__name__)


def run_backtest(
    historical_data: List[HistoricalPrice],
    strategy_input: StrategyInput,
    benchmark_data: Optional[List[HistoricalPrice]] = None
) -> StrategyResult:
    """
    Runs backtest for RSI + MA20 strategy with SIP and optional dip buying.
    
    Optimized for performance with detailed timing logs.
    """
    start_time = time.time()
    logger.info(f"=" * 80)
    logger.info(f"BACKTEST START: {strategy_input.symbol}")
    logger.info(f"Date range: {strategy_input.start_date} to {strategy_input.end_date}")
    logger.info(f"=" * 80)
    
    if not historical_data:
        logger.warning("No historical data provided for backtest")
        return _create_empty_result("No historical data available")
    
    try:
        # Step 1: Convert SQLAlchemy models to DataFrame
        step_start = time.time()
        logger.info(f"Step 1: Converting {len(historical_data)} records to DataFrame...")
        
        # Convert SQLAlchemy models to dict
        data_dicts = []
        for hp in historical_data:
            data_dicts.append({
                'date': hp.date,
                'open': float(hp.open) if hp.open else 0.0,
                'high': float(hp.high) if hp.high else 0.0,
                'low': float(hp.low) if hp.low else 0.0,
                'close': float(hp.close),
                'volume': int(hp.volume) if hp.volume else 0
            })
        
        df = pd.DataFrame(data_dicts)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        
        logger.info(f"Step 1 DONE in {time.time() - step_start:.2f}s - DataFrame shape: {df.shape}")
        
        if df.empty or 'close' not in df.columns:
            logger.error("Invalid historical data structure")
            return _create_empty_result("Invalid historical data")
        
        # Step 2: Filter to date range
        step_start = time.time()
        logger.info(f"Step 2: Filtering to date range...")
        
        df = df.loc[strategy_input.start_date:strategy_input.end_date]
        
        logger.info(f"Step 2 DONE in {time.time() - step_start:.2f}s - {len(df)} rows after filtering")
        
        if df.empty:
            logger.warning("No data in specified date range")
            return _create_empty_result("No data in date range")
        
        # Step 3: Clean data
        step_start = time.time()
        logger.info(f"Step 3: Cleaning data (forward fill and dropna)...")
        
        df['close'] = df['close'].ffill()
        df = df.dropna(subset=['close'])
        
        logger.info(f"Step 3 DONE in {time.time() - step_start:.2f}s - {len(df)} rows after cleaning")
        
        if len(df) < 15:
            logger.warning(f"Insufficient data points: {len(df)}")
            return _create_empty_result("Insufficient data points for backtest")
        
        # Step 4: Calculate RSI
        step_start = time.time()
        logger.info(f"Step 4: Calculating RSI (14 period) on {len(df)} rows...")
        
        df['rsi'] = calculate_rsi(df['close'].tolist(), period=14)
        
        logger.info(f"Step 4 DONE in {time.time() - step_start:.2f}s")
        
        # Step 5: Calculate MA20
        step_start = time.time()
        logger.info(f"Step 5: Calculating MA20 on {len(df)} rows...")
        
        df['ma20'] = calculate_ma(df['close'].tolist(), period=20)
        
        logger.info(f"Step 5 DONE in {time.time() - step_start:.2f}s")
        
        # Step 6: Run simulation
        step_start = time.time()
        logger.info(f"Step 6: Running backtest simulation...")
        
        sip_amount = strategy_input.sip_amount
        dip_multiplier = strategy_input.dip_multiplier or 1.0
        
        cash_balance = 0.0
        units_accumulated = 0.0
        transactions: List[TransactionRecord] = []
        equity_curve: List[DailyPortfolioValue] = []
        xirr_transactions: List[Dict[str, Any]] = []
        total_investment = 0.0
        
        last_sip_year_month = None
        transaction_count = 0
        equity_count = 0
        
        # Track progress
        total_rows = len(df)
        progress_interval = max(100, total_rows // 10)
        rows_processed = 0
        
        for current_date, row in df.iterrows():
            rows_processed += 1
            
            if rows_processed % progress_interval == 0:
                logger.info(f"  Progress: {rows_processed}/{total_rows} rows ({rows_processed/total_rows*100:.1f}%)")
            
            current_close = row['close']
            current_rsi = row['rsi']
            current_ma20 = row['ma20']
            
            if pd.isna(current_close) or current_close <= 0:
                continue
            
            current_date_obj = current_date.date()
            year_month = (current_date.year, current_date.month)
            
            # Monthly SIP
            if year_month != last_sip_year_month:
                cash_balance += sip_amount
                total_investment += sip_amount
                xirr_transactions.append({
                    'date': current_date_obj,
                    'amount': -sip_amount
                })
                transactions.append(TransactionRecord(
                    date=current_date_obj,
                    type=TransactionType.SIP,
                    quantity=0.0,
                    price_per_unit=current_close,
                    amount=sip_amount,
                    cash_balance=cash_balance,
                    units_accumulated=units_accumulated
                ))
                last_sip_year_month = year_month
                transaction_count += 1
            
            # Dip buying
            if (current_rsi is not None and current_ma20 is not None and
                not pd.isna(current_rsi) and not pd.isna(current_ma20)):
                
                if current_rsi < 30 and current_close < current_ma20 and cash_balance > 0:
                    max_buy_amount = sip_amount * dip_multiplier
                    buy_amount = min(cash_balance, max_buy_amount)
                    
                    if buy_amount > 0:
                        units_to_buy = buy_amount / current_close
                        cash_balance -= buy_amount
                        units_accumulated += units_to_buy
                        
                        transactions.append(TransactionRecord(
                            date=current_date_obj,
                            type=TransactionType.DIP_BUY,
                            quantity=units_to_buy,
                            price_per_unit=current_close,
                            amount=buy_amount,
                            cash_balance=cash_balance,
                            units_accumulated=units_accumulated
                        ))
                        transaction_count += 1
            
            # Record portfolio value weekly
            if current_date.dayofweek == 0 or current_date == df.index[-1]:
                portfolio_value = units_accumulated * current_close + cash_balance
                equity_curve.append(DailyPortfolioValue(
                    date=current_date_obj,
                    value=portfolio_value
                ))
                equity_count += 1
        
        logger.info(f"Step 6 DONE in {time.time() - step_start:.2f}s")
        logger.info(f"  Transactions: {transaction_count}, Equity points: {equity_count}")
        
        # Step 7: Calculate metrics
        step_start = time.time()
        logger.info(f"Step 7: Calculating final metrics...")
        
        if not equity_curve:
            logger.warning("No equity curve generated")
            return _create_empty_result("Backtest failed to generate results")
        
        final_portfolio_value = equity_curve[-1].value
        absolute_return = final_portfolio_value - total_investment
        absolute_return_pct = (absolute_return / total_investment * 100) if total_investment > 0 else 0.0
        
        # XIRR
        xirr_transactions.append({
            'date': equity_curve[-1].date,
            'amount': final_portfolio_value
        })
        
        xirr_start = time.time()
        xirr_value = calculate_xirr(xirr_transactions)
        logger.info(f"  XIRR calculation: {time.time() - xirr_start:.2f}s")
        if xirr_value is not None:
            xirr_value = xirr_value * 100
        
        # CAGR
        cagr_value = calculate_cagr(
            start_value=total_investment,
            end_value=final_portfolio_value,
            start_date=equity_curve[0].date,
            end_date=equity_curve[-1].date
        )
        if cagr_value is not None:
            cagr_value = cagr_value * 100
        
        # Max drawdown
        equity_values = [point.value for point in equity_curve]
        max_dd = calculate_max_drawdown(equity_values)
        if max_dd is not None:
            max_dd = max_dd * 100
        
        logger.info(f"Step 7 DONE in {time.time() - step_start:.2f}s")
        
        # Step 8: Process benchmark
        step_start = time.time()
        logger.info(f"Step 8: Processing benchmark...")
        
        benchmark_curve, benchmark_return = _process_benchmark(
            benchmark_data,
            sip_amount,
            df.index.min().date(),
            df.index.max().date()
        )
        
        logger.info(f"Step 8 DONE in {time.time() - step_start:.2f}s")
        
        # Create summary
        summary = SummaryStatistics(
            total_investment=total_investment,
            final_portfolio_value=final_portfolio_value,
            absolute_return=absolute_return,
            absolute_return_pct=absolute_return_pct,
            xirr=xirr_value,
            benchmark_return=benchmark_return,
            cagr=cagr_value,
            max_drawdown=max_dd,
            message="Backtest completed successfully"
        )
        
        total_time = time.time() - start_time
        logger.info(f"=" * 80)
        logger.info(f"BACKTEST COMPLETE in {total_time:.2f}s")
        logger.info(f"Investment: ₹{total_investment:.2f}")
        logger.info(f"Final Value: ₹{final_portfolio_value:.2f}")
        logger.info(f"Return: {absolute_return_pct:.2f}%")
        logger.info(f"XIRR: {xirr_value:.2f}%" if xirr_value else "XIRR: N/A")
        logger.info(f"=" * 80)
        
        return StrategyResult(
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            transactions=transactions,
            summary_stats=summary,
            message="Backtest completed successfully"
        )
        
    except Exception as e:
        logger.error(f"ERROR in backtest after {time.time() - start_time:.2f}s: {e}", exc_info=True)
        return _create_empty_result(f"Backtest error: {str(e)}")


def _process_benchmark(
    benchmark_data: Optional[List[HistoricalPrice]],
    sip_amount: float,
    start_date: date,
    end_date: date
) -> tuple[List[DailyPortfolioValue], Optional[float]]:
    """Process benchmark data."""
    if not benchmark_data:
        logger.info("  No benchmark data provided")
        return [], None
    
    try:
        bench_start = time.time()
        logger.info(f"  Processing {len(benchmark_data)} benchmark records...")
        
        # Convert SQLAlchemy models to dict
        data_dicts = []
        for hp in benchmark_data:
            data_dicts.append({
                'date': hp.date,
                'close': float(hp.close)
            })
        
        benchmark_df = pd.DataFrame(data_dicts)
        benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
        benchmark_df = benchmark_df.set_index('date').sort_index()
        
        # Filter to date range
        benchmark_df = benchmark_df.loc[start_date:end_date]
        
        if benchmark_df.empty or 'close' not in benchmark_df.columns:
            logger.warning("  Invalid benchmark data")
            return [], None
        
        # Forward fill
        benchmark_df['close'] = benchmark_df['close'].ffill()
        benchmark_df = benchmark_df.dropna(subset=['close'])
        
        logger.info(f"  Benchmark cleaned: {len(benchmark_df)} rows")
        
        # Simulate monthly SIP
        benchmark_units = 0.0
        benchmark_investment = 0.0
        benchmark_curve: List[DailyPortfolioValue] = []
        last_sip_year_month = None
        
        for b_date, b_row in benchmark_df.iterrows():
            b_close = b_row['close']
            
            if pd.isna(b_close) or b_close <= 0:
                continue
            
            year_month = (b_date.year, b_date.month)
            
            if year_month != last_sip_year_month:
                benchmark_investment += sip_amount
                benchmark_units += sip_amount / b_close
                last_sip_year_month = year_month
            
            # Weekly recording
            if b_date.dayofweek == 0 or b_date == benchmark_df.index[-1]:
                benchmark_value = benchmark_units * b_close
                benchmark_curve.append(DailyPortfolioValue(
                    date=b_date.date(),
                    value=benchmark_value
                ))
        
        # Calculate return
        if benchmark_investment > 0 and benchmark_curve:
            final_benchmark_value = benchmark_curve[-1].value
            benchmark_return = ((final_benchmark_value - benchmark_investment) / 
                              benchmark_investment * 100)
        else:
            benchmark_return = None
        
        logger.info(f"  Benchmark done in {time.time() - bench_start:.2f}s: {len(benchmark_curve)} points, return={benchmark_return:.2f}%" if benchmark_return else "  Benchmark done: no return calculated")
        
        return benchmark_curve, benchmark_return
        
    except Exception as e:
        logger.error(f"  Error processing benchmark: {e}")
        return [], None


def _create_empty_result(message: str) -> StrategyResult:
    """Create an empty StrategyResult for error cases."""
    return StrategyResult(
        equity_curve=[],
        benchmark_curve=[],
        transactions=[],
        summary_stats=SummaryStatistics(
            total_investment=0.0,
            final_portfolio_value=0.0,
            absolute_return=0.0,
            absolute_return_pct=0.0,
            message=message
        ),
        message=message
    )