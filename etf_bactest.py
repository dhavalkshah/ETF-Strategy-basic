from openchart import NSEData
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from scipy.optimize import newton

# ---------------------
# Helper function for XIRR calculation
# ---------------------
def xirr(transactions):
    """
    transactions: list of tuples (date, amount)
    Positive amount = inflow (redemption), Negative amount = outflow (investment)
    """
    def xnpv(rate):
        return sum([amount / ((1 + rate) ** ((date - transactions[0][0]).days / 365.0))
                    for date, amount in transactions])

    # Use Newton's method to solve for rate
    return newton(lambda r: xnpv(r), 0.1)


# ---------------------
# Backtest function
# ---------------------
def backtest_etf_strategy(etf_symbol='NIFTYBEES', start_date='2010-01-01'):
    nse = NSEData()
    nse.download()
    end_date = datetime.datetime.now()

    start_date = pd.to_datetime(start_date)

    # Download NIFTY 50 and ETF data
    nifty_df = nse.historical(
        symbol='Nifty 50',
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

    # Merge both datasets
    df = pd.merge(etf_df, nifty_df, on='date', suffixes=('_ETF', '_NIFTY'))
    df['NIFTY_Return'] = df['Close_NIFTY'].pct_change()

    carry_over = 0
    total_units = 0
    total_invested = 0
    records = []
    transactions = []  # to store (date, cashflow)

    for i in range(1, len(df)):
        date = df.loc[i, 'date']
        close_price = df.loc[i, 'Close_ETF']
        nifty_return = df.loc[i, 'NIFTY_Return']

        if nifty_return < 0:
            invest_amount = 1000 + carry_over
            units_bought = invest_amount / close_price
            total_units += units_bought
            total_invested += invest_amount
            carry_over = 0
            transactions.append((date, -invest_amount))  # Outflow
        else:
            invest_amount = 0
            units_bought = 0
            carry_over += 1000

        current_value = total_units * close_price

        records.append({
            'Date': date,
            'ETF Close': round(close_price, 2),
            'NIFTY Return': round(nifty_return, 4),
            'Invested Today': round(invest_amount, 2),
            'Total Invested': round(total_invested, 2),
            'Units Bought': round(units_bought, 4),
            'Total Units': round(total_units, 4),
            'Portfolio Value': round(current_value, 2),
            'NIFTY Close': round(df.loc[i, 'Close_NIFTY'], 2)
        })

    result_df = pd.DataFrame(records)

    # Add final redemption value (inflow)
    transactions.append((result_df.iloc[-1]['Date'], result_df.iloc[-1]['Portfolio Value']))

    # Calculate XIRR
    try:
        irr = xirr(transactions)
        xirr_percent = irr * 100
    except Exception as e:
        print("XIRR calculation failed:", e)
        xirr_percent = None

    # Export
    # CSV file name = ETF symbol + _backtest.csv
    csv_filename = f"{etf_symbol}_backtest.csv"

    result_df.to_csv(csv_filename, index=False)
    print(f"Exported to etf_backtest.csv")
    print(f"Total Invested: ₹{result_df.iloc[-1]['Total Invested']:.2f}")
    print(f"Final Portfolio Value: ₹{result_df.iloc[-1]['Portfolio Value']:.2f}")
    if xirr_percent:
        print(f"XIRR: {xirr_percent:.2f}%")

    # ---------------------
    # Plotting
    # ---------------------
    plt.figure(figsize=(12, 6))
    plt.plot(result_df['Date'], result_df['Portfolio Value'], label='ETF Portfolio Value', color='green')
    plt.plot(result_df['Date'], result_df['Total Invested'], label='Total Invested', color='blue', linestyle='--')

    # Normalize NIFTY for comparison (base = first value)
    nifty_normalized = (result_df['NIFTY Close'] / result_df['NIFTY Close'].iloc[0]) * result_df['Total Invested'].iloc[-1]
    plt.plot(result_df['Date'], nifty_normalized, label='NIFTY 50 Benchmark', color='orange')

    plt.title(f'ETF ({etf_symbol}) vs NIFTY 50 Benchmark\nXIRR: {xirr_percent:.2f}%')
    plt.xlabel('Date')
    plt.ylabel('Amount (₹)')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


# ---------------------
# Run the strategy
# ---------------------

def main():
    #get user input for ETF symbol and start date
    etf_symbol = input("Enter ETF symbol (default: NIFTYBEES): ") or 'NIFTYBEES'
    start_date = input("Enter start date (YYYY-MM-DD, default: 2020-01-01): ") or '2020-01-01'
    backtest_etf_strategy(etf_symbol, start_date)

if __name__ == "__main__":
    main()