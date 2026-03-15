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
    OPTIMIZED DAILY SIP STRATEGY with Market-Based Signals
    
    Strategy:
    1. Uses BENCHMARK (NIFTY 50) for market timing, not ETF price
    2. Daily base SIP with dip buying when market crashes
    3. Carry-over mechanism: saves money during bull runs, deploys during crashes
    4. Dip strength weighting: bigger crashes get bigger investments
    
    Signals from BENCHMARK:
    - MA20: 20-day moving average of benchmark
    - RSI: Relative strength of benchmark
    - Daily Return: % change in benchmark
    
    Investment Decision:
    - Normal day: Invest base amount, accumulate carry-over
    - Dip day (benchmark down, below MA20, RSI < 45):
      → Invest base + portion of carry-over + (dip_strength × multiplier)
    """
    start_time = time.time()
    logger.info(f"=" * 80)
    logger.info(f"OPTIMIZED BACKTEST START: {strategy_input.symbol}")
    logger.info(f"Strategy: Market-Based Daily SIP with Smart Dip Buying")
    logger.info(f"Base SIP: ₹{strategy_input.sip_amount}/day")
    logger.info(f"Date range: {strategy_input.start_date} to {strategy_input.end_date}")
    logger.info(f"=" * 80)
    
    if not historical_data:
        logger.warning("No historical data provided for backtest")
        return _create_empty_result("No historical data available")
    
    if not benchmark_data:
        logger.warning("No benchmark data provided - cannot run market-based strategy")
        return _create_empty_result("Benchmark data required for this strategy")
    
    try:
        # Step 1: Convert ETF data to DataFrame
        step_start = time.time()
        logger.info(f"Step 1: Converting {len(historical_data)} ETF records to DataFrame...")
        
        etf_data_dicts = []
        for hp in historical_data:
            etf_data_dicts.append({
                'date': hp.date,
                'etf_close': float(hp.close),
                'etf_open': float(hp.open) if hp.open else 0.0,
                'etf_high': float(hp.high) if hp.high else 0.0,
                'etf_low': float(hp.low) if hp.low else 0.0,
            })
        
        etf_df = pd.DataFrame(etf_data_dicts)
        etf_df['date'] = pd.to_datetime(etf_df['date'])
        etf_df = etf_df.set_index('date').sort_index()
        
        logger.info(f"Step 1 DONE in {time.time() - step_start:.2f}s - ETF data: {etf_df.shape}")
        
        # Step 2: Convert benchmark data to DataFrame
        step_start = time.time()
        logger.info(f"Step 2: Converting {len(benchmark_data)} benchmark records...")
        
        benchmark_data_dicts = []
        for hp in benchmark_data:
            benchmark_data_dicts.append({
                'date': hp.date,
                'benchmark_close': float(hp.close)
            })
        
        benchmark_df = pd.DataFrame(benchmark_data_dicts)
        benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
        benchmark_df = benchmark_df.set_index('date').sort_index()
        
        logger.info(f"Step 2 DONE in {time.time() - step_start:.2f}s - Benchmark data: {benchmark_df.shape}")
        
        # Step 3: Merge ETF and Benchmark data
        step_start = time.time()
        logger.info(f"Step 3: Merging ETF and benchmark data...")
        
        df = pd.merge(
            etf_df,
            benchmark_df,
            left_index=True,
            right_index=True,
            how='inner'
        )
        
        # Filter to strategy date range
        df = df.loc[strategy_input.start_date:strategy_input.end_date]
        
        logger.info(f"Step 3 DONE in {time.time() - step_start:.2f}s - Merged data: {df.shape}")
        
        if df.empty:
            logger.warning("No data after merge")
            return _create_empty_result("No overlapping data between ETF and benchmark")
        
        # Step 4: Clean data
        step_start = time.time()
        logger.info(f"Step 4: Cleaning and forward filling...")
        
        df['etf_close'] = df['etf_close'].ffill()
        df['benchmark_close'] = df['benchmark_close'].ffill()
        df = df.dropna(subset=['etf_close', 'benchmark_close'])
        
        logger.info(f"Step 4 DONE in {time.time() - step_start:.2f}s - {len(df)} clean rows")
        
        if len(df) < 20:
            logger.warning(f"Insufficient data points: {len(df)}")
            return _create_empty_result("Insufficient data points for backtest")
        
        # Step 5: Calculate BENCHMARK indicators (KEY DIFFERENCE!)
        step_start = time.time()
        logger.info(f"Step 5: Calculating BENCHMARK indicators...")
        
        # Calculate benchmark daily returns
        df['benchmark_return'] = df['benchmark_close'].pct_change()
        
        # Calculate MA20 on BENCHMARK
        df['benchmark_ma20'] = calculate_ma(df['benchmark_close'].tolist(), period=20)
        
        # Calculate RSI on BENCHMARK
        df['benchmark_rsi'] = calculate_rsi(df['benchmark_close'].tolist(), period=14)
        
        logger.info(f"Step 5 DONE in {time.time() - step_start:.2f}s")
        logger.info(f"  Using BENCHMARK for all signals (not ETF)")
        
        # Step 6: Run OPTIMIZED simulation
        step_start = time.time()
        logger.info(f"Step 6: Running optimized backtest...")
        
        base_sip_amount = strategy_input.sip_amount
        dip_multiplier = strategy_input.dip_multiplier or 1.0
        carry_util_fraction = strategy_input.carry_over_fraction or 0.5  # Use 50% of carry-over per dip
        
        # Initialize
        carry_over = 0.0
        units_accumulated = 0.0
        total_investment = 0.0
        
        transactions: List[TransactionRecord] = []
        equity_curve: List[DailyPortfolioValue] = []
        xirr_transactions: List[Dict[str, Any]] = []
        
        # Statistics
        regular_days = 0
        dip_days = 0
        max_carry_over = 0.0
        
        total_rows = len(df)
        progress_interval = max(100, total_rows // 10)
        rows_processed = 0
        
        for current_date, row in df.iterrows():
            rows_processed += 1
            
            if rows_processed % progress_interval == 0:
                logger.info(f"  Progress: {rows_processed}/{total_rows} ({rows_processed/total_rows*100:.1f}%)")
            
            etf_price = row['etf_close']
            benchmark_return = row['benchmark_return']
            benchmark_ma20 = row['benchmark_ma20']
            benchmark_rsi = row['benchmark_rsi']
            
            # Skip if any indicator is missing
            if pd.isna(etf_price) or pd.isna(benchmark_return) or pd.isna(benchmark_ma20) or pd.isna(benchmark_rsi):
                continue
            
            current_date_obj = current_date.date()
            
            # Determine if today is a MARKET DIP DAY
            is_dip_day = (
                benchmark_return < 0 and                          # Market down today
                row['benchmark_close'] < benchmark_ma20 and       # Below 20-day MA
                benchmark_rsi < 45                                # Market oversold
            )
            
            # Calculate dip strength (how severe is the crash?)
            dip_strength = abs(benchmark_return) if is_dip_day else 0.0
            
            # Determine investment amount
            if is_dip_day:
                # DIP DAY: Deploy aggressively
                # Base + portion of carry_over + dip bonus
                carry_over_deploy = carry_over * carry_util_fraction
                dip_bonus = dip_strength * dip_multiplier * 1000  # Scale to reasonable amount
                
                investment_today = base_sip_amount + carry_over_deploy + dip_bonus
                
                # Reduce carry_over
                carry_over = carry_over * (1 - carry_util_fraction)
                
                transaction_type = TransactionType.DIP_BUY
                dip_days += 1
                
            else:
                # REGULAR DAY: Invest base amount and accumulate carry-over
                investment_today = 0
                carry_over += base_sip_amount  # Save for future dips
                
                transaction_type = TransactionType.SIP
                regular_days += 1
            
            # Track max carry-over
            max_carry_over = max(max_carry_over, carry_over)

            if investment_today > 0:
                # Execute investment
                total_investment += investment_today
                units_bought = investment_today / etf_price
                units_accumulated += units_bought
            
                # Record for XIRR
                xirr_transactions.append({
                    'date': current_date_obj,
                    'amount': -investment_today
                })

                # Record transaction
                transactions.append(TransactionRecord(
                    date=current_date_obj,
                    type=transaction_type,
                    quantity=units_bought,
                    price_per_unit=etf_price,
                    amount=investment_today,
                    cash_balance=carry_over,  # Show carry_over as "cash balance"
                    units_accumulated=units_accumulated
                ))
            
            
            # Record portfolio value weekly
            # if current_date.dayofweek == 0 or current_date == df.index[-1]:
                portfolio_value = units_accumulated * etf_price
                equity_curve.append(DailyPortfolioValue(
                    date=current_date_obj,
                    value=portfolio_value
                ))
        
        logger.info(f"Step 6 DONE in {time.time() - step_start:.2f}s")
        logger.info(f"  Total trading days: {regular_days + dip_days}")
        logger.info(f"  Regular days: {regular_days}")
        logger.info(f"  Dip buying days: {dip_days} ({dip_days/(regular_days+dip_days)*100:.1f}%)")
        logger.info(f"  Max carry-over accumulated: ₹{max_carry_over:.2f}")
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
        
        xirr_value = calculate_xirr(xirr_transactions)
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
        
        # Step 8: Process benchmark (also with daily SIP for comparison)
        step_start = time.time()
        logger.info(f"Step 8: Processing benchmark...")
        
        benchmark_curve, benchmark_return = _process_benchmark_daily_sip(
            benchmark_data,
            base_sip_amount,
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
            message="Optimized market-based strategy completed successfully"
        )
        
        total_time = time.time() - start_time
        logger.info(f"=" * 80)
        logger.info(f"OPTIMIZED BACKTEST COMPLETE in {total_time:.2f}s")
        logger.info(f"Total Investment: ₹{total_investment:.2f}")
        logger.info(f"Final Value: ₹{final_portfolio_value:.2f}")
        logger.info(f"Absolute Return: {absolute_return_pct:.2f}%")
        logger.info(f"XIRR: {xirr_value:.2f}%" if xirr_value else "XIRR: N/A")
        logger.info(f"CAGR: {cagr_value:.2f}%" if cagr_value else "CAGR: N/A")
        logger.info(f"Benchmark Return: {benchmark_return:.2f}%" if benchmark_return else "Benchmark: N/A")
        logger.info(f"=" * 80)
        
        return StrategyResult(
            equity_curve=equity_curve,
            benchmark_curve=benchmark_curve,
            transactions=transactions,
            summary_stats=summary,
            message="Optimized market-based strategy completed successfully"
        )
        
    except Exception as e:
        logger.error(f"ERROR in backtest after {time.time() - start_time:.2f}s: {e}", exc_info=True)
        return _create_empty_result(f"Backtest error: {str(e)}")

def _process_benchmark_daily_sip(
    benchmark_data: Optional[List[HistoricalPrice]],
    daily_sip_amount: float,
    start_date: date,
    end_date: date
) -> tuple[List[DailyPortfolioValue], Optional[float]]:
    """
    Process benchmark with simple daily SIP (no dip buying).
    
    Returns:
        - benchmark_curve: Weekly portfolio values for visualization
        - benchmark_xirr: XIRR % (annualized return) for fair comparison
    """
    if not benchmark_data:
        logger.info("  No benchmark data provided")
        return [], None
    
    try:
        bench_start = time.time()
        logger.info(f"  Processing benchmark with simple daily SIP...")
        
        # Convert to DataFrame
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
        
        if benchmark_df.empty:
            logger.warning("  Empty benchmark data after filtering")
            return [], None
        
        # Clean data
        benchmark_df['close'] = benchmark_df['close'].ffill()
        benchmark_df = benchmark_df.dropna(subset=['close'])
        
        logger.info(f"  Benchmark cleaned: {len(benchmark_df)} rows")
        
        # Simulate daily SIP in benchmark
        benchmark_units = 0.0
        benchmark_investment = 0.0
        benchmark_curve: List[DailyPortfolioValue] = []
        benchmark_xirr_transactions: List[Dict[str, Any]] = []
        
        for b_date, b_row in benchmark_df.iterrows():
            b_close = b_row['close']
            
            if pd.isna(b_close) or b_close <= 0:
                continue
            
            # Daily SIP
            benchmark_investment += daily_sip_amount
            benchmark_units += daily_sip_amount / b_close
            
            # Record transaction for XIRR (negative = outflow)
            benchmark_xirr_transactions.append({
                'date': b_date.date(),
                'amount': -daily_sip_amount
            })
            
            # Weekly recording for visualization
            if b_date.dayofweek == 0 or b_date == benchmark_df.index[-1]:
                benchmark_value = benchmark_units * b_close
                benchmark_curve.append(DailyPortfolioValue(
                    date=b_date.date(),
                    value=benchmark_value
                ))
        
        # Calculate XIRR
        if benchmark_investment > 0 and benchmark_curve:
            final_value = benchmark_curve[-1].value
            
            # Add final redemption for XIRR (positive = inflow)
            benchmark_xirr_transactions.append({
                'date': benchmark_curve[-1].date,
                'amount': final_value
            })
            
            # Calculate XIRR
            benchmark_xirr = calculate_xirr(benchmark_xirr_transactions)
            
            if benchmark_xirr is not None:
                benchmark_xirr = benchmark_xirr * 100  # Convert to percentage
                logger.info(f"  Benchmark XIRR: {benchmark_xirr:.2f}%")
            else:
                logger.warning("  Benchmark XIRR calculation failed")
                # Fallback to absolute return if XIRR fails
                benchmark_xirr = ((final_value - benchmark_investment) / benchmark_investment * 100)
                logger.info(f"  Benchmark absolute return (fallback): {benchmark_xirr:.2f}%")
        else:
            benchmark_xirr = None
            logger.warning("  No benchmark investment to calculate return")
        
        logger.info(f"  Benchmark done in {time.time() - bench_start:.2f}s")
        logger.info(f"  Benchmark: ₹{benchmark_investment:.2f} invested, {len(benchmark_xirr_transactions)-1} transactions")
        
        return benchmark_curve, benchmark_xirr
        
    except Exception as e:
        logger.error(f"  Error processing benchmark: {e}", exc_info=True)
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

def _list_to_csv(lst: List[Dict[str, Any]], filename: str) -> None:
    """Utility to save list of dicts to CSV for debugging."""
    df = pd.DataFrame(lst)
    df.to_csv(filename, index=False)
    logger.info(f"Saved debug data to {filename}")