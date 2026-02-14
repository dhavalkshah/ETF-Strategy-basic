from openchart import NSEData
import pandas as pd
import datetime
import numpy as np
import os


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
# Daily Investment Advisor
# ---------------------
def daily_investment_advisor(
    etf_symbol='NIFTYBEES',
    csv_file='etf_investment_log.csv',
    dip_multiplier=50000,
    carry_util_frac=0.5,
    base_invest=1000,
    start_date='2025-11-03',
    benchmark_symbol='NIFTY 50'
):
    """
    Analyzes current market conditions and prescribes today's investment amount.
    Updates the CSV with actual transactions.
    """
    
    nse = NSEData()
    nse.download()
    
    today = datetime.datetime.now().date()
    start_date = pd.to_datetime(start_date).date()
    
    print(f"\n{'='*60}")
    print(f"📊 Daily Investment Advisor - {etf_symbol}")
    print(f"📅 Date: {today}")
    print(f"{'='*60}\n")
    
    # --- Load or Create CSV ---
    if os.path.exists(csv_file):
        portfolio_df = pd.read_csv(csv_file)
        portfolio_df['Date'] = pd.to_datetime(portfolio_df['Date']).dt.date
        
        # Get last state
        if len(portfolio_df) > 0:
            last_row = portfolio_df.iloc[-1]
            carry_over = last_row['Carry Over']
            total_units = last_row['Total Units']
            total_invested = last_row['Total Invested']
            print(f"📂 Loaded existing portfolio from {csv_file}")
            print(f"   Last updated: {last_row['Date']}")
            print(f"   Total invested so far: ₹{total_invested:,.2f}")
            print(f"   Total units: {total_units:.4f}")
            print(f"   Carry over: ₹{carry_over:,.2f}\n")
        else:
            carry_over = 0
            total_units = 0
            total_invested = 0
            print(f"📂 Loaded empty portfolio file\n")
    else:
        portfolio_df = pd.DataFrame()
        carry_over = 0
        total_units = 0
        total_invested = 0
        print(f"📝 Creating new portfolio file: {csv_file}\n")
    
    # --- Download Market Data ---
    print("⏳ Fetching market data...")
    
    # Get 40 days of data to ensure we have enough for 20-day MA
    data_start = start_date - datetime.timedelta(days=40)
    
    nifty_df = nse.historical(
        symbol=benchmark_symbol,
        exchange='NSE',
        start=data_start,
        end=today,
        interval='1d'
    )
    nifty_df['date'] = nifty_df.index.date
    
    etf_df = nse.historical(
        symbol=etf_symbol,
        exchange='NSE',
        start=data_start,
        end=today,
        interval='1d'
    )
    etf_df['date'] = etf_df.index.date
    
    # --- Merge and Calculate Indicators ---
    df = pd.merge(etf_df, nifty_df, on='date', suffixes=('_ETF', '_NIFTY'))
    df['NIFTY_Return'] = df['Close_NIFTY'].pct_change()
    df['MA20'] = df['Close_NIFTY'].rolling(20).mean()
    df['RSI'] = compute_rsi(df['Close_NIFTY'])
    df = df.dropna()
    
    # --- Check if today's data exists ---
    today_data = df[df['date'] == today]
    
    if len(today_data) == 0:
        print("❌ No market data available for today.")
        print("   Market might be closed or data not yet updated.")
        print("   Please try again later.\n")
        return
    
    # --- Get Today's Values ---
    row = today_data.iloc[-1]
    close_price = row['Close_ETF']
    nifty_return = row['NIFTY_Return']
    ma20 = row['MA20']
    rsi = row['RSI']
    nifty_close = row['Close_NIFTY']
    
    # --- Display Market Conditions ---
    print(f"✅ Market data retrieved\n")
    print(f"📈 Market Conditions:")
    print(f"   {etf_symbol} Price: ₹{close_price:.2f}")
    print(f"   NIFTY 50: {nifty_close:.2f}")
    print(f"   NIFTY Return: {nifty_return*100:.2f}%")
    print(f"   20-Day MA: {ma20:.2f}")
    print(f"   RSI: {rsi:.2f}\n")
    
    # --- Calculate Investment Amount ---
    dip_strength = abs(nifty_return) if nifty_return < 0 else 0
    
    # Check strategy conditions
    is_dip = nifty_return < 0
    below_ma = nifty_close < ma20
    rsi_low = rsi < 45
    
    print(f"🎯 Strategy Signals:")
    print(f"   Dip detected: {'✅ YES' if is_dip else '❌ NO'} (return < 0)")
    print(f"   Below MA20: {'✅ YES' if below_ma else '❌ NO'}")
    print(f"   RSI < 45: {'✅ YES' if rsi_low else '❌ NO'}\n")
    
    if is_dip and below_ma and rsi_low:
        additional_dip_invest = dip_strength * dip_multiplier
        carry_invest = carry_over * carry_util_frac
        invest_amount = base_invest + carry_invest + additional_dip_invest
        new_carry_over = carry_over * (1 - carry_util_frac)
        
        print(f"🟢 BUY SIGNAL TRIGGERED!")
        print(f"   Base investment: ₹{base_invest:,.2f}")
        print(f"   From carry-over ({carry_util_frac*100:.0f}%): ₹{carry_invest:,.2f}")
        print(f"   Dip bonus: ₹{additional_dip_invest:,.2f}")
        print(f"   {'─'*50}")
        print(f"   💰 RECOMMENDED INVESTMENT: ₹{invest_amount:,.2f}")
        print(f"   Units to buy (approx): {invest_amount/close_price:.4f}")
        print(f"   New carry-over: ₹{new_carry_over:,.2f}\n")
        
    else:
        invest_amount = 0
        new_carry_over = carry_over + base_invest
        
        print(f"🟡 NO BUY SIGNAL - Hold cash")
        print(f"   Adding ₹{base_invest:,.2f} to carry-over")
        print(f"   New carry-over: ₹{new_carry_over:,.2f}\n")
    
    # --- Prompt for Actual Transaction ---
    print(f"{'─'*60}\n")
    response = input("Did you make a transaction today? (y/n): ").strip().lower()
    
    if response == 'y':
        actual_amount = float(input("Enter actual amount invested (₹): "))
        actual_units = float(input("Enter units purchased: "))
        actual_price = float(input("Enter actual price per unit (₹): "))
        
        # Update portfolio
        total_invested += actual_amount
        total_units += actual_units
        
        # If user didn't follow recommendation, adjust carry-over accordingly
        if invest_amount > 0:
            # They were supposed to buy
            carry_over = new_carry_over
        else:
            # They bought when not recommended - don't add to carry-over
            carry_over = new_carry_over - base_invest
        
    else:
        actual_amount = 0
        actual_units = 0
        actual_price = close_price
        carry_over = new_carry_over
    
    # --- Calculate Portfolio Value ---
    portfolio_value = total_units * close_price
    
    # --- Save to CSV ---
    new_row = {
        'Date': today,
        'ETF Close': round(close_price, 2),
        'NIFTY Close': round(nifty_close, 2),
        'NIFTY Return': round(nifty_return, 4),
        'RSI': round(rsi, 2),
        'MA20': round(ma20, 2),
        'Recommended Investment': round(invest_amount, 2),
        'Actual Investment': round(actual_amount, 2),
        'Actual Units': round(actual_units, 4),
        'Actual Price': round(actual_price, 2),
        'Carry Over': round(carry_over, 2),
        'Total Invested': round(total_invested, 2),
        'Total Units': round(total_units, 4),
        'Portfolio Value': round(portfolio_value, 2)
    }
    
    portfolio_df = pd.concat([portfolio_df, pd.DataFrame([new_row])], ignore_index=True)
    portfolio_df.to_csv(csv_file, index=False)
    
    print(f"\n✅ Portfolio updated and saved to {csv_file}")
    print(f"\n📊 Current Portfolio Summary:")
    print(f"   Total invested: ₹{total_invested:,.2f}")
    print(f"   Total units: {total_units:.4f}")
    print(f"   Current value: ₹{portfolio_value:,.2f}")
    print(f"   Gain/Loss: ₹{portfolio_value - total_invested:,.2f} ({(portfolio_value/total_invested - 1)*100:.2f}%)")
    print(f"   Carry-over for next time: ₹{carry_over:,.2f}\n")


# ---------------------
# Main Function
# ---------------------
def main():
    print("\n🚀 ETF Daily Investment Advisor\n")
    
    # Get configuration
    etf_symbol = input("Enter ETF symbol (default: NIFTYBEES): ").strip() or 'NIFTYBEES'
    benchmark_symbol = input("Enter benchmark index symbol (default: NIFTY 50): ").strip() or 'NIFTY 50'
    csv_file = input(f"Enter CSV filename (default: {etf_symbol}_log.csv): ").strip() or f'{etf_symbol}_log.csv'
    
    # Optional: customize parameters
    customize = input("\nCustomize strategy parameters? (y/n, default: n): ").strip().lower()
    
    if customize == 'y':
        base_invest = float(input("Base daily SIP amount (default: 1000): ") or 1000)
        dip_multiplier = float(input("Dip multiplier (default: 50000): ") or 50000)
        carry_util_frac = float(input("Carry-over utilization fraction (default: 0.5): ") or 0.5)
    else:
        base_invest = 1000
        dip_multiplier = 50000
        carry_util_frac = 0.5
    
    # Run advisor
    daily_investment_advisor(
        etf_symbol=etf_symbol,
        csv_file=csv_file,
        dip_multiplier=dip_multiplier,
        carry_util_frac=carry_util_frac,
        base_invest=base_invest,
        start_date='2025-11-03',
        benchmark_symbol=benchmark_symbol
    )


if __name__ == "__main__":
    main()