import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

from app.strategy.calculations import calculate_rsi, calculate_ma, calculate_xirr
from app.strategy.models import StrategyInput, StrategyResult, DailyPortfolioValue, TransactionRecord, SummaryStatistics
from app.db.models import HistoricalPrice

def run_backtest(historical_data: List[HistoricalPrice], strategy_input: StrategyInput, benchmark_data: Optional[List[HistoricalPrice]] = None) -> StrategyResult:
    """
    Runs the backtest for the RSI + MA20 strategy with SIP and optional dip buying.
    """
    if not historical_data:
        return StrategyResult(
            equity_curve=[],
            transactions=[],
            summary_stats=SummaryStatistics(total_investment=0, final_portfolio_value=0, absolute_return=0)
        )

    df = pd.DataFrame([hp.model_dump() for hp in historical_data])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    # Ensure all dates from start_date to end_date are present
    full_date_range = pd.date_range(start=strategy_input.start_date, end=strategy_input.end_date, freq='D')
    df = df.reindex(full_date_range).fillna(method='ffill').fillna(method='bfill') # Fill missing dates

    # Calculate indicators
    df['rsi'] = calculate_rsi(df['close'].tolist())
    df['ma20'] = calculate_ma(df['close'].tolist())

    # Strategy parameters
    sip_amount = strategy_input.sip_amount
    dip_multiplier = strategy_input.dip_multiplier if strategy_input.dip_multiplier is not None else 1.0
    carry_over_fraction = strategy_input.carry_over_fraction

    # Initialize portfolio
    cash_balance = 0.0
    units_accumulated = 0.0
    transactions: List[TransactionRecord] = []
    equity_curve: List[DailyPortfolioValue] = []
    investment_transactions_for_xirr: List[Dict[str, Any]] = [] # For XIRR calculation
    total_investment = 0.0
    
    # Track monthly SIP
    last_sip_month = None

    for current_date, row in df.iterrows():
        current_close = row['close']
        current_rsi = row['rsi']
        current_ma20 = row['ma20']

        if pd.isna(current_close): # Skip if no price data for the day
            continue

        # Daily portfolio value
        current_portfolio_value = units_accumulated * current_close + cash_balance
        equity_curve.append(DailyPortfolioValue(date=current_date.date(), value=current_portfolio_value))

        # SIP Logic (monthly)
        if current_date.month != last_sip_month and current_date.day >= 1 and current_date.day <= 5: # SIP on first 5 days of month
            cash_balance += sip_amount
            total_investment += sip_amount
            investment_transactions_for_xirr.append({'date': current_date.date(), 'amount': -sip_amount})
            transactions.append(TransactionRecord(
                date=current_date.date(),
                type="SIP",
                quantity=0, price_per_unit=0, amount=sip_amount,
                cash_balance=cash_balance, units_accumulated=units_accumulated
            ))
            last_sip_month = current_date.month

        # Trading Logic (RSI + MA20)
        if current_rsi is not None and current_ma20 is not None:
            # Buy condition: RSI < 30 and price below MA20
            if current_rsi < 30 and current_close < current_ma20:
                buy_amount = min(cash_balance, sip_amount * dip_multiplier) # Buy up to dip_multiplier * SIP amount
                
                if buy_amount > 0:
                    units_to_buy = buy_amount / current_close
                    cash_balance -= buy_amount
                    units_accumulated += units_to_buy
                    investment_transactions_for_xirr.append({'date': current_date.date(), 'amount': -buy_amount})
                    transactions.append(TransactionRecord(
                        date=current_date.date(),
                        type="BUY",
                        quantity=units_to_buy,
                        price_per_unit=current_close,
                        amount=buy_amount,
                        cash_balance=cash_balance,
                        units_accumulated=units_accumulated
                    ))

    # Calculate final portfolio value
    final_portfolio_value = units_accumulated * df['close'].iloc[-1] + cash_balance
    absolute_return = (final_portfolio_value - total_investment) / total_investment * 100 if total_investment > 0 else 0

    # For XIRR, add final portfolio value as a positive cash flow
    if final_portfolio_value > 0:
        investment_transactions_for_xirr.append({'date': df.index[-1].date(), 'amount': final_portfolio_value})
    
    # Calculate XIRR
    xirr_value = calculate_xirr(investment_transactions_for_xirr)

    # Calculate benchmark curve
    benchmark_equity_curve: List[DailyPortfolioValue] = []
    benchmark_return: Optional[float] = None
    if benchmark_data:
        benchmark_df = pd.DataFrame([hp.model_dump() for hp in benchmark_data])
        benchmark_df['date'] = pd.to_datetime(benchmark_df['date'])
        benchmark_df = benchmark_df.set_index('date').sort_index()
        benchmark_df = benchmark_df.reindex(full_date_range).fillna(method='ffill').fillna(method='bfill')

        initial_benchmark_investment = 0.0
        current_benchmark_value = 0.0
        
        # Simple benchmark: invest SIP amount in benchmark on the same SIP days
        benchmark_total_investment = 0.0
        benchmark_units = 0.0
        last_benchmark_sip_month = None

        for b_date, b_row in benchmark_df.iterrows():
            if pd.isna(b_row['close']):
                continue

            # Monthly SIP for benchmark
            if b_date.month != last_benchmark_sip_month and b_date.day >= 1 and b_date.day <= 5:
                benchmark_total_investment += sip_amount
                benchmark_units += sip_amount / b_row['close']
                last_benchmark_sip_month = b_date.month
            
            benchmark_equity_curve.append(DailyPortfolioValue(date=b_date.date(), value=benchmark_units * b_row['close']))

        if benchmark_total_investment > 0 and benchmark_units > 0 and not benchmark_equity_curve:
             final_benchmark_value = benchmark_units * benchmark_df['close'].iloc[-1]
             benchmark_return = (final_benchmark_value - benchmark_total_investment) / benchmark_total_investment * 100
        elif benchmark_equity_curve:
            benchmark_return = (benchmark_equity_curve[-1].value - benchmark_equity_curve[0].value) / benchmark_equity_curve[0].value * 100 if benchmark_equity_curve[0].value > 0 else 0


    summary = SummaryStatistics(
        total_investment=total_investment,
        final_portfolio_value=final_portfolio_value,
        absolute_return=absolute_return,
        xirr=xirr_value,
        benchmark_return=benchmark_return
    )

    return StrategyResult(
        equity_curve=equity_curve,
        benchmark_curve=benchmark_equity_curve,
        transactions=transactions,
        summary_stats=summary,
        message="Backtest completed successfully"
    )