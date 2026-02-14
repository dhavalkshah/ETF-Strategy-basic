import pandas as pd
import datetime
import matplotlib.pyplot as plt
from scipy.optimize import newton
import numpy as np
import requests

# ---------------------
# Helper: XIRR
# ---------------------
def xirr(transactions):
    def xnpv(rate):
        return sum([amt / ((1 + rate) ** ((date - transactions[0][1]).days / 365.0))
                    for amt, date in transactions])
    return newton(lambda r: xnpv(r), 0.1)

# ---------------------
# Fetch NAV history for a scheme
# ---------------------
def fetch_nav_history(scheme_code):
    """
    Returns DataFrame with columns: ['date', 'nav']
    scheme_code: e.g. 'INF205KA1494'
    Uses MFAPI (just as one example)
    """
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    resp = requests.get(url)
    data = resp.json()
    # data['data'] is list of dicts {'date': 'dd-mm-yyyy', 'nav': 'xx.xx'}
    recs = []
    for item in data.get('data', []):
        d = pd.to_datetime(item['date'], format="%d-%m-%Y")
        nav = float(item['nav'])
        recs.append({'date': d, 'nav': nav})
    df = pd.DataFrame(recs)
    df = df.sort_values('date').reset_index(drop=True)
    return df

# ---------------------
# Strategy: SIP + Dip Enhancer for MF
# ---------------------
def backtest_mutual_fund_strategy(
    scheme_code,
    start_date='2010-01-01',
    base_sip=1000.0,
    dip_multiplier=20000.0,
    carry_util_frac=0.5,
    momentum_ma_days=20,
    momentum_rsi_thresh=45
):
    # Fetch NAV history
    nav_df = fetch_nav_history(scheme_code)
    nav_df = nav_df[nav_df['date'] >= pd.to_datetime(start_date)].copy()
    nav_df = nav_df.reset_index(drop=True)

    # Calculate returns, MA, RSI
    nav_df['ret'] = nav_df['nav'].pct_change()
    nav_df['MA'] = nav_df['nav'].rolling(momentum_ma_days).mean()

    # RSI
    delta = nav_df['nav'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    nav_df['RSI'] = 100 - (100 / (1 + rs))

    carry_over = 0.0
    total_units = 0.0
    total_invested = 0.0
    records = []
    transactions = []

    for i in range(momentum_ma_days + 1, len(nav_df)):
        date = nav_df.loc[i, 'date']
        nav = nav_df.loc[i, 'nav']
        ret = nav_df.loc[i, 'ret']
        ma = nav_df.loc[i, 'MA']
        rsi = nav_df.loc[i, 'RSI']
        dip_strength = abs(ret) if ret < 0 else 0.0

        invest_amount = base_sip  # you always at least SIP
        extra = 0.0
        if (ret < 0) and (nav < ma) and (rsi < momentum_rsi_thresh):
            extra = (carry_over * carry_util_frac) + (dip_strength * dip_multiplier)
            invest_amount += extra
            # deduct carry-over used fraction
            carry_over = carry_over * (1 - carry_util_frac)

        else:
            # no extra, carry forward SIP amount
            carry_over += base_sip

        # buy units at NAV
        units = invest_amount / nav
        total_units += units
        total_invested += invest_amount

        # record cashflow (outflow)
        transactions.append((-invest_amount, date))

        portfolio_value = total_units * nav

        records.append({
            'date': date,
            'nav': nav,
            'invested_today': invest_amount,
            'extra_amount': extra,
            'carry_over': carry_over,
            'total_invested': total_invested,
            'total_units': total_units,
            'portfolio_value': portfolio_value,
            'MA': ma,
            'RSI': rsi
        })

    # final redemption
    final_date = nav_df.iloc[-1]['date']
    final_nav = nav_df.iloc[-1]['nav']
    final_portfolio = total_units * final_nav
    transactions.append((final_portfolio, final_date))

    result_df = pd.DataFrame(records)

    # XIRR
    try:
        irr = xirr(transactions)
        xirr_pct = irr * 100
    except Exception as e:
        print("XIRR fail:", e)
        xirr_pct = None

    # Metrics
    result_df['daily_ret'] = result_df['portfolio_value'].pct_change()
    cum_return = result_df['portfolio_value'].iloc[-1] / result_df['total_invested'].iloc[-1] - 1
    vol = result_df['daily_ret'].std() * np.sqrt(252)
    sharpe = (cum_return - 0.06) / vol if vol > 0 else np.nan
    max_dd = ((result_df['portfolio_value'] / result_df['portfolio_value'].cummax()) - 1).min() * 100

    # Print summary
    csv_filename = f"{scheme_code}_backtest.csv"
    result_df.to_csv(csv_filename, index=False)
    print("Scheme:", scheme_code)
    print("Total Invested:", total_invested)
    print("Final Value:", final_portfolio)
    if xirr_pct is not None:
        print("XIRR:", f"{xirr_pct:.2f}%")
    print("CAGR (approx):", f"{cum_return * 100:.2f}%")
    print("Max Drawdown:", f"{max_dd:.2f}%")
    print("Sharpe:", f"{sharpe:.2f}")

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(result_df['date'], result_df['portfolio_value'], label='Portfolio Value')
    plt.plot(result_df['date'], result_df['total_invested'], label='Total Invested', linestyle='--')
    plt.title(f"SIP + Dip Strategy for {scheme_code}")
    plt.xlabel("Date")
    plt.ylabel("Value (₹)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    return result_df, xirr_pct

def main():
    #get user input for ETF symbol and start date
    etf_symbol = input("Enter MF symbol (default: INF205KA1494): ") or 'INF205KA1494'
    start_date = input("Enter start date (YYYY-MM-DD, default: 2020-01-01): ") or '2020-01-01'
    backtest_mutual_fund_strategy(etf_symbol, start_date)

if __name__ == "__main__":
    main()
