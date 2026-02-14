from openchart import NSEData
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from scipy.optimize import newton
import numpy as np

#https://charting.nseindia.com/Charts/GetEQMasters -- Master list for NSE

# ---------------------
# Helper function for XIRR
# ---------------------
def xirr(transactions):
    """
    transactions: list of tuples (date, amount)
    Positive amount = inflow, Negative = outflow
    """
    def xnpv(rate):
        return sum([
            amount / ((1 + rate) ** ((date - transactions[0][0]).days / 365.0))
            for date, amount in transactions
        ])
    return newton(lambda r: xnpv(r), 0.1)


# ---------------------
# RSI Calculation
# ---------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ---------------------
# Backtest Function
# ---------------------
def backtest_etf_strategy(etf_symbol='NIFTYBEES', 
    start_date='2010-01-01', 
    dip_multiplier=50000,         # scales dip intensity
    carry_util_frac=0.5,          # fraction of carry-over utilized each buy
    base_invest=1000,           # base SIP amount
    benchmark_symbol='NIFTY 50'
):
    nse = NSEData()
    nse.download()
    end_date = datetime.datetime.now()

    start_date = pd.to_datetime(start_date)

    # --- Download Data ---
    nifty_df = nse.historical(
        symbol=benchmark_symbol,
        exchange='NSE',
        start=start_date,
        end=end_date,
        interval='1d'
    )
    nifty_df['date'] = nifty_df.index

    etf_df = nse.historical(
        symbol=etf_symbol,
        exchange='NSE',
        start=start_date,
        end=end_date,
        interval='1d'
    )
    etf_df['date'] = etf_df.index

    # --- Merge Data ---
    df = pd.merge(etf_df, nifty_df, on='date', suffixes=('_ETF', '_NIFTY'))
    df['NIFTY_Return'] = df['Close_NIFTY'].pct_change()

    # --- Indicators ---
    df['MA20'] = df['Close_NIFTY'].rolling(20).mean()
    df['RSI'] = compute_rsi(df['Close_NIFTY'])

    carry_over = 0
    total_units = 0
    total_invested = 0
    records = []
    transactions = []

    # --- Core Logic ---
    for i in range(20, len(df)):
        date = df.loc[i, 'date']
        close_price = df.loc[i, 'Close_ETF']
        nifty_return = df.loc[i, 'NIFTY_Return']
        ma20 = df.loc[i, 'MA20']
        rsi = df.loc[i, 'RSI']
        dip_strength = abs(nifty_return) if nifty_return < 0 else 0

        # Weighted Dip + Momentum Filter
        if (nifty_return < 0) and (df.loc[i, 'Close_NIFTY'] < ma20) and (rsi < 45):
            invest_amount = base_invest + (carry_over * carry_util_frac) + (dip_strength * dip_multiplier)
            carry_over = carry_over * (1 - carry_util_frac)
            units_bought = invest_amount / close_price
            total_units += units_bought
            total_invested += invest_amount
            transactions.append((date, -invest_amount))
        else:
            invest_amount = 0
            units_bought = 0
            carry_over += 1000

        current_value = total_units * close_price

        records.append({
            'Date': date,
            'ETF Close': round(close_price, 2),
            'NIFTY Return': round(nifty_return, 4),
            'RSI': round(rsi, 2),
            'MA20': round(ma20, 2),
            'Invested Today': round(invest_amount, 2),
            'Carry Over': round(carry_over, 2),
            'Additional Invest': round((dip_strength * dip_multiplier), 2),
            'Total Invested': round(total_invested, 2),
            'Units Bought': round(units_bought, 4),
            'Total Units': round(total_units, 4),
            'Portfolio Value': round(current_value, 2),
            'NIFTY Close': round(df.loc[i, 'Close_NIFTY'], 2)
        })

    result_df = pd.DataFrame(records)

    # --- Final Redemption ---
    transactions.append((result_df.iloc[-1]['Date'], result_df.iloc[-1]['Portfolio Value']))

    # --- XIRR ---
    try:
        irr = xirr(transactions)
        xirr_percent = irr * 100
    except Exception as e:
        print("XIRR calculation failed:", e)
        xirr_percent = None

    # --- Performance Metrics ---
    result_df['Daily_Return'] = result_df['Portfolio Value'].pct_change()
    cumulative_return = (result_df['Portfolio Value'].iloc[-1] / result_df['Total Invested'].iloc[-1]) - 1
    volatility = result_df['Daily_Return'].std() * np.sqrt(252)
    sharpe_ratio = (cumulative_return - 0.06) / volatility if volatility > 0 else 0
    max_drawdown = ((result_df['Portfolio Value'] / result_df['Portfolio Value'].cummax()) - 1).min() * 100

    # --- Export + Summary ---
    csv_filename = f"{etf_symbol}_backtest.csv"
    result_df.to_csv(csv_filename, index=False)
    print(f"\n✅ Exported to etf_backtest_refined.csv")
    print(f"Total Invested: ₹{result_df.iloc[-1]['Total Invested']:.2f}")
    print(f"Final Portfolio Value: ₹{result_df.iloc[-1]['Portfolio Value']:.2f}")
    if xirr_percent:
        print(f"XIRR: {xirr_percent:.2f}%")
    print(f"CAGR: {cumulative_return*100:.2f}%")
    print(f"Max Drawdown: {max_drawdown:.2f}%")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

    # --- Plot ---
    plt.figure(figsize=(12, 6))
    plt.plot(result_df['Date'], result_df['Portfolio Value'], label='ETF Portfolio', color='green')
    plt.plot(result_df['Date'], result_df['Total Invested'], label='Total Invested', color='blue', linestyle='--')

    # Benchmark: Normalize Nifty to same base
    nifty_normalized = (result_df['NIFTY Close'] / result_df['NIFTY Close'].iloc[0]) * result_df['Total Invested'].iloc[-1]
    plt.plot(result_df['Date'], nifty_normalized, label='NIFTY 50 Benchmark', color='orange')

    plt.title(f"{etf_symbol} Smart Dip Strategy vs NIFTY 50\nXIRR: {xirr_percent:.2f}% | Max DD: {max_drawdown:.2f}% | Sharpe: {sharpe_ratio:.2f}")
    plt.xlabel("Date")
    plt.ylabel("Amount (₹)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# ---------------------
# Run Strategy
# ---------------------
def main():
    #get user input for ETF symbol and start date
    etf_symbol = input("Enter ETF symbol (default: NIFTYBEES): ") or 'NIFTYBEES'
    start_date = input("Enter start date (YYYY-MM-DD, default: 2020-01-01): ") or '2020-01-01'
    benchmark_symbol = input("Enter benchmark index symbol (default: NIFTY 50): ") or 'NIFTY 50'
    backtest_etf_strategy(etf_symbol, start_date, benchmark_symbol=benchmark_symbol)

if __name__ == "__main__":
    main()
