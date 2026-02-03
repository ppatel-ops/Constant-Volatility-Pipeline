import io
import zipfile
import pandas as pd
import requests
from datetime import date, timedelta
from config import NSE_BASE_URL, HEADERS


# NSE Market Holidays Exceptions (dates that are holidays but have market data)
NSE_EXCEPTIONS = {
    "2026-02-01",  # Exception: Market open despite being a holiday
}

# NSE Holidays by Year (can be extended for future years)
NSE_HOLIDAYS_BY_YEAR = {
    2024: {
        "2024-01-26",  # Republic Day
        "2024-03-08",  # Maha Shivaratri
        "2024-03-25",  # Holi
        "2024-03-29",  # Good Friday
        "2024-04-11",  # Eid ul-Fitr
        "2024-04-17",  # Ram Navami
        "2024-04-21",  # Mahavir Jayanti
        "2024-05-23",  # Buddha Purnima
        "2024-06-17",  # Eid ul-Adha
        "2024-07-17",  # Muharram
        "2024-08-15",  # Independence Day
        "2024-08-26",  # Janmashtami
        "2024-09-16",  # Milad un-Nabi
        "2024-10-02",  # Gandhi Jayanti
        "2024-10-12",  # Dussehra
        "2024-10-31",  # Diwali
        "2024-11-01",  # Diwali (Day 2)
        "2024-11-15",  # Guru Nanak Jayanti
        "2024-12-25",  # Christmas
    },
    2025: {
        "2025-01-26",  # Republic Day
        "2025-02-28",  # Maha Shivaratri
        "2025-03-14",  # Holi
        "2025-04-18",  # Good Friday
        "2025-03-30",  # Eid ul-Fitr
        "2025-04-04",  # Ram Navami
        "2025-04-14",  # Ambedkar Jayanti
        "2025-04-21",  # Mahavir Jayanti
        "2025-05-23",  # Buddha Purnima
        "2025-06-07",  # Eid ul-Adha
        "2025-07-07",  # Muharram
        "2025-08-15",  # Independence Day
        "2025-08-16",  # Janmashtami
        "2025-09-16",  # Milad un-Nabi
        "2025-10-02",  # Gandhi Jayanti
        "2025-10-02",  # Gandhi Jayanti
        "2025-10-20",  # Dussehra
        "2025-10-20",  # Dushera
        "2025-11-01",  # Diwali
        "2025-11-05",  # Diwali (Day 2)
        "2025-11-15",  # Guru Nanak Jayanti
        "2025-12-25",  # Christmas
    },
    2026: {
        "2026-01-26",  # Republic Day
        "2026-03-06",  # Maha Shivaratri
        "2026-03-25",  # Holi
        "2026-04-10",  # Good Friday
        "2026-04-14",  # Eid ul-Fitr
        "2026-04-21",  # Ram Navami
        "2026-05-01",  # Maharashtra Day
        "2026-08-15",  # Independence Day
        "2026-10-02",  # Gandhi Jayanti
        "2026-10-24",  # Dussehra
        "2026-11-12",  # Diwali
        "2026-12-25",  # Christmas
    },
    2027: {
        "2027-01-26",  # Republic Day
        "2027-02-19",  # Maha Shivaratri
        "2027-03-14",  # Holi
        "2027-04-02",  # Good Friday
        "2027-05-01",  # Maharashtra Day
        "2027-05-14",  # Buddha Purnima
        "2027-08-15",  # Independence Day
        "2027-10-02",  # Gandhi Jayanti
        "2027-10-15",  # Dussehra
        "2027-11-01",  # Diwali
        "2027-11-15",  # Guru Nanak Jayanti
        "2027-12-25",  # Christmas
    }
}


def get_nse_holidays(year):
    """
    Get NSE holidays for a specific year
    Returns: Set of holiday dates in YYYY-MM-DD format, or empty set if year not defined
    """
    return NSE_HOLIDAYS_BY_YEAR.get(year, set())


def is_market_holiday(date_obj):
    """Check if a date is a market holiday or weekend"""
    date_str = date_obj.strftime("%Y-%m-%d")
    
    # Check if date is in exceptions (market open despite being a holiday)
    if date_str in NSE_EXCEPTIONS:
        return False
    
    # Weekends are always holidays
    if date_obj.weekday() >= 5:  # Sat/Sun
        return True
    
    # Check NSE holidays for the given year
    year = date_obj.year
    nse_holidays = get_nse_holidays(year)
    return date_str in nse_holidays


def get_previous_working_day(date_obj):
    """Get the previous working day"""
    prev_day = date_obj - timedelta(days=1)

    while is_market_holiday(prev_day):
        prev_day -= timedelta(days=1)
    return prev_day


class NSEFOBhavcopyFetcher:
    """Fetches F&O data from NSE bhavcopy archives"""
    
    BASE_URL = "https://nsearchives.nseindia.com/content/fo/"
    HEADERS = {"User-Agent": "Mozilla/5.0"}

    # -----------------------------------------------
    # Download + extract bhavcopy
    # -----------------------------------------------
    def _download_and_extract(self, fetch_date: date) -> pd.DataFrame:
        """Downloads and extracts the NSE F&O Bhavcopy for a specific date."""
        date_str = fetch_date.strftime("%Y%m%d")
        filename = f"BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv"
        zip_name = filename + ".zip"

        url = self.BASE_URL + zip_name
        print(f"[*] Fetching: {url}")
        
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to download data for {fetch_date}: {e}")

        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                with zf.open(filename) as f:
                    df = pd.read_csv(f)
            return df
        except zipfile.BadZipFile:
            raise ValueError("Downloaded file is not a valid zip archive.")
        except KeyError:
            raise ValueError(f"CSV file {filename} not found inside the zip.")

    # -----------------------------------------------
    # Filter futures
    # -----------------------------------------------
    def _filter_futures(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Filters dataframe for futures only"""
        futures = df[
            (df["TckrSymb"] == ticker) &
            (df["FinInstrmTp"].isin(["IDF", "STF"]))
        ].copy()

        futures["XpryDt"] = pd.to_datetime(futures["XpryDt"])
        futures.sort_values("XpryDt", inplace=True)

        return futures

    # -----------------------------------------------
    # Filter weekly options
    # -----------------------------------------------
    def _filter_weekly_options(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Filters dataframe for weekly options only (nearest expiry)"""
        options = df[
            (df["TckrSymb"] == ticker) &
            (df["FinInstrmTp"].isin(["IDO", "STO"]))
        ].copy()

        options["XpryDt"] = pd.to_datetime(options["XpryDt"])

        if options.empty:
            raise ValueError(f"No options data found for {ticker}")

        # Weekly expiry = nearest expiry
        weekly_expiry = options["XpryDt"].min()
        weekly_options = options[options["XpryDt"] == weekly_expiry].copy()

        # Select useful columns
        weekly_options = weekly_options[[
            "XpryDt",
            "StrkPric",
            "OptnTp",      # CE / PE
            "ClsPric",
            "OpnIntrst"
        ]]
        
        # Filter for liquid options (close price >= 5)
        weekly_options = weekly_options[weekly_options["ClsPric"] >= 5]

        return weekly_options.reset_index(drop=True)

    # -----------------------------------------------
    # Public API
    # -----------------------------------------------
    def fetch_futures(self, ticker: str, fetch_date: date) -> pd.DataFrame:
        """Fetch futures data for a ticker"""
        bhavcopy_df = self._download_and_extract(fetch_date)
        futures_df = self._filter_futures(bhavcopy_df, ticker)

        if futures_df.empty:
            raise ValueError(f"No futures data found for {ticker}")

        return futures_df

    def fetch_weekly_options(self, ticker: str, fetch_date: date) -> pd.DataFrame:
        """Fetch weekly options data for a ticker"""
        bhavcopy_df = self._download_and_extract(fetch_date)
        weekly_options_df = self._filter_weekly_options(bhavcopy_df, ticker)

        return weekly_options_df

    def fetch_spot_price(self, ticker: str, fetch_date: date) -> float:
        """Get spot price from nearest month futures"""
        futures_df = self.fetch_futures(ticker, fetch_date)

        nearest_expiry = futures_df["XpryDt"].min()
        front = futures_df[futures_df["XpryDt"] == nearest_expiry]

        if front.empty:
            raise ValueError("No front month future found")

        spot_price = round(float(front.iloc[0]["ClsPric"]), 2)
        return spot_price


class DataFetcher:
    """Legacy wrapper for backward compatibility"""
    
    fetcher = NSEFOBhavcopyFetcher()

    @staticmethod
    def fetch_bhavcopy(fetch_date: date):
        """Downloads and extracts the NSE F&O Bhavcopy for a specific date."""
        return DataFetcher.fetcher._download_and_extract(fetch_date)

    @staticmethod
    def filter_data(df, symbol):
        """Filters the bhavcopy for a specific symbol."""
        df_filtered = df[df['SYMBOL'] == symbol].copy()
        if df_filtered.empty:
            raise ValueError(f"No data found for symbol: {symbol}")
        return df_filtered
    
    @staticmethod
    def fetch_futures(ticker: str, fetch_date: date):
        """Fetch futures data"""
        return DataFetcher.fetcher.fetch_futures(ticker, fetch_date)
    
    @staticmethod
    def fetch_weekly_options(ticker: str, fetch_date: date):
        """Fetch weekly options data"""
        return DataFetcher.fetcher.fetch_weekly_options(ticker, fetch_date)
    
    @staticmethod
    def fetch_spot_price(ticker: str, fetch_date: date) -> float:
        """Get spot price from futures"""
        return DataFetcher.fetcher.fetch_spot_price(ticker, fetch_date)