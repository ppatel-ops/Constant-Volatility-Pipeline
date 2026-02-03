from datetime import date
from fetcher import DataFetcher, get_previous_working_day, is_market_holiday

# ==========================================
# FETCH BHAVCOPY FOR SPECIFIC DATE
# ==========================================
def fetch_any_date(year, month, day):
    """
    Fetch bhavcopy for a specific date.
    Strategy: Try the given date first. If data is not available,
    check if it's a holiday and try previous working day.
    """
    fetch_date = date(year, month, day)
    print(f"Attempting to fetch data for {fetch_date}...")
    
    try:
        bhavcopy_df = DataFetcher.fetch_bhavcopy(fetch_date)
        print(f"✓ Successfully fetched data for {fetch_date}")
        return bhavcopy_df
    except Exception as e:
        # Data not available for given date, check if it's a holiday
        if is_market_holiday(fetch_date):
            print(f"⚠ Data not available for {fetch_date} (market holiday). Trying previous working day...")
            try:
                prev_date = get_previous_working_day(fetch_date)
                bhavcopy_df = DataFetcher.fetch_bhavcopy(prev_date)
                print(f"✓ Successfully fetched data for {prev_date}")
                return bhavcopy_df
            except Exception as e2:
                print(f"✗ Error fetching data for previous working day {prev_date}: {e2}")
                return None
        else:
            print(f"✗ Error: No data available for {fetch_date}: {e}")
            return None

# ==========================================
# FETCH WITH TICKER FILTERING
# ==========================================
def fetch_ticker_data(ticker, year, month, day):
    """
    Fetch specific ticker data for a given date.
    Strategy: Try the given date first. If data is not available,
    check if it's a holiday and try previous working day.
    """
    fetch_date = date(year, month, day)
    print(f"\nAttempting to fetch {ticker} data for {fetch_date}...")
    
    try:
        # Fetch futures
        futures = DataFetcher.fetch_futures(ticker, fetch_date)
        spot = DataFetcher.fetch_spot_price(ticker, fetch_date)
        options = DataFetcher.fetch_weekly_options(ticker, fetch_date)
        
        print(f"✓ Successfully fetched {ticker} data for {fetch_date}")
        return futures, spot, options
        
    except Exception as e:
        # Data not available for given date, check if it's a holiday
        if is_market_holiday(fetch_date):
            print(f"⚠ Data not available for {fetch_date} (market holiday). Trying previous working day...")
            try:
                prev_date = get_previous_working_day(fetch_date)
                futures = DataFetcher.fetch_futures(ticker, prev_date)
                spot = DataFetcher.fetch_spot_price(ticker, prev_date)
                options = DataFetcher.fetch_weekly_options(ticker, prev_date)
                
                print(f"✓ Successfully fetched {ticker} data for {prev_date}")
                return futures, spot, options
            except Exception as e2:
                print(f"✗ Error fetching {ticker} data for previous working day {prev_date}: {e2}")
                return None, None, None
        else:
            print(f"✗ Error: No {ticker} data available for {fetch_date}: {e}")
            return None, None, None

# ==========================================
# MAIN - INPUT YOUR DATE HERE
# ==========================================
if __name__ == "__main__":
    # Example: Fetch bhavcopy for a specific date
    print("=" * 60)
    print("BHAVCOPY FETCHER - INPUT YOUR DATE")
    print("=" * 60)
    
    # Input date (YYYY, MM, DD)
    year = int(input("Enter year (e.g., 2026): "))
    month = int(input("Enter month (1-12): "))
    day = int(input("Enter day (1-31): "))
    
    # Fetch full bhavcopy
    print("\n" + "=" * 60)
    print(f"FETCHING BHAVCOPY DATA FOR {year}-{month:02d}-{day:02d}")
    print("=" * 60)
    bhavcopy = fetch_any_date(year, month, day)
    if bhavcopy is not None:
        print(f"\nTotal records: {len(bhavcopy)}")
        print("\nFirst 5 rows:")
        print(bhavcopy.head())
    
    # Optional: Fetch ticker-specific data
    print("\n" + "=" * 60)
    fetch_ticker = input("Do you want to fetch ticker-specific data? (yes/no): ").lower()
    
    if fetch_ticker == "yes":
        ticker = input("Enter ticker symbol (e.g., BANKNIFTY, NIFTY): ").upper()
        print("\n" + "=" * 60)
        print(f"FETCHING {ticker} DATA FOR {year}-{month:02d}-{day:02d}")
        print("=" * 60)
        futures, spot, options = fetch_ticker_data(ticker, year, month, day)
        if futures is not None:
            print(f"\n{'='*30} FUTURES {'='*30}")
            print(futures)
            print(f"\n{'='*30} SPOT PRICE {'='*30}")
            print(f"Spot Price: {spot}")
            print(f"\n{'='*30} WEEKLY OPTIONS {'='*30}")
            print(options)