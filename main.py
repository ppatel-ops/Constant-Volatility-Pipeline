import sys
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import os

from fetcher import DataFetcher, NSEFOBhavcopyFetcher, is_market_holiday, get_previous_working_day
from strategy import (
    attach_premiums_from_bhavcopy, 
    get_atm_options,
    pnl_curve,
    expected_metrics,
    StrategyManager
)
from visualizer import Visualizer
from analytics import implied_vol, compute_ttm


def fetch_bhavcopy_safe(fetcher, fetch_date):
    """Try to fetch bhavcopy for a date, return None if fails"""
    try:
        return fetcher.fetch_weekly_options("NIFTY", fetch_date)
    except Exception:
        return None


def load_user_bhavcopy(file_path):
    """
    Load bhavcopy data from user-provided CSV file
    Returns: DataFrame with weekly options data, or None if file not found
    """
    if not os.path.exists(file_path):
        print(f"⚠️ Bhavcopy file not found at: {file_path}")
        return None
    
    try:
        bhavcopy_data = pd.read_csv(file_path)
        print(f"✅ Loaded bhavcopy data from: {file_path}")
        print(f"   Records: {len(bhavcopy_data)}")
        return bhavcopy_data
    except Exception as e:
        print(f"❌ Error reading bhavcopy file: {e}")
        return None


def validate_bhavcopy_data(bhavcopy_data, valuation_date):
    """
    Validate bhavcopy data against valuation date
    Ensures:
    1. Bhavcopy date is not greater than valuation date
    2. Expiry date in bhavcopy is after valuation date
    """
    try:
        # Get the date of bhavcopy data
        if 'TradDt' in bhavcopy_data.columns:
            bhavcopy_date = pd.to_datetime(bhavcopy_data['TradDt'].iloc[0]).date()
        elif 'BizDt' in bhavcopy_data.columns:
            bhavcopy_date = pd.to_datetime(bhavcopy_data['BizDt'].iloc[0]).date()
        else:
            raise ValueError("Cannot determine bhavcopy data date - missing TradDt or BizDt column")
        
        print(f"[*] Bhavcopy date: {bhavcopy_date}")
        print(f"[*] Valuation date: {valuation_date}")
        
        # Check 1: Bhavcopy date should not be in the future compared to valuation date
        if bhavcopy_date > valuation_date:
            raise ValueError(
                f"❌ Bhavcopy date ({bhavcopy_date}) is later than valuation date ({valuation_date}). "
                f"Please provide bhavcopy data from the valuation date or earlier."
            )
        
        print(f"✅ Bhavcopy date is valid (≤ valuation date)")
        
        # Check 2: Ensure expiry dates are in the future
        options = bhavcopy_data[
            (bhavcopy_data['TckrSymb'] == 'NIFTY') & 
            (bhavcopy_data['FinInstrmTp'].isin(['IDO', 'STO']))
        ].copy()
        
        if not options.empty:
            options['XpryDt'] = pd.to_datetime(options['XpryDt'])
            nearest_expiry = options['XpryDt'].min().date()
            
            print(f"[*] Nearest expiry in bhavcopy: {nearest_expiry}")
            
            if nearest_expiry <= valuation_date:
                raise ValueError(
                    f"❌ Nearest expiry date ({nearest_expiry}) is not after valuation date ({valuation_date}). "
                    f"Please provide bhavcopy data with options expiring after the valuation date."
                )
            
            print(f"✅ Expiry dates are valid (after valuation date)")
        
        return True
    
    except Exception as e:
        raise ValueError(f"Bhavcopy validation failed: {str(e)}")


def extract_spot_price_from_futures(bhavcopy_data, symbol):

    """
    Extract spot price from futures data in bhavcopy
    Returns: spot price (float)
    """
    try:
        # Filter for NIFTY futures
        futures_data = bhavcopy_data[
            (bhavcopy_data['TckrSymb'] == symbol) & 
            (bhavcopy_data['FinInstrmTp'].isin(['IDF', 'STF']))
        ]
        
        if futures_data.empty:
            print(f"⚠️ No futures data found for {symbol}")
            return None
        
        # Get the most recent futures contract (closest expiry)
        futures_data['XpryDt'] = pd.to_datetime(futures_data['XpryDt'])
        latest_future = futures_data.sort_values('XpryDt').iloc[0]
        
        spot_price = latest_future['ClsPric']
        print(f"✅ Spot price from futures: {spot_price}")
        return spot_price
    
    except Exception as e:
        print(f"❌ Error extracting spot price: {e}")
        return None


def extract_weekly_options_from_bhavcopy(bhavcopy_data, symbol):
    """
    Extract weekly options data from user-provided bhavcopy
    Returns: DataFrame with weekly options contracts (nearest expiry)
    """
    try:
        # Filter for options (OPTIDX)
        options = bhavcopy_data[
            (bhavcopy_data['TckrSymb'] == symbol) & 
            (bhavcopy_data['FinInstrmTp'].isin(['IDO', 'STO']))
        ].copy()
        
        if options.empty:
            print(f"❌ No options data found in bhavcopy for {symbol}")
            return None
        
        # Convert expiry date to datetime
        options['XpryDt'] = pd.to_datetime(options['XpryDt'])
        
        # Get the NEAREST expiry date (not just Wednesday)
        nearest_expiry = options['XpryDt'].min()
        
        # Filter for options with nearest expiry date
        weekly_opts = options[options['XpryDt'] == nearest_expiry].copy()
        
        print(f"✅ Extracted {len(weekly_opts)} weekly options contracts")
        if not weekly_opts.empty:
            print(f"   Nearest expiry: {nearest_expiry.date()}")
        
        return weekly_opts
    
    except Exception as e:
        print(f"❌ Error extracting weekly options: {e}")
        return None


def get_iv_reference_date(ticker, valuation_date):
    """
    Get the IV reference date (skips holidays and weekends, looks back for available data)
    """
    print(f"🔍 Checking IV reference date for {valuation_date}")

    fetcher = NSEFOBhavcopyFetcher()

    # Step 1: Move to previous working day (skipping weekends & holidays)
    ref_date = get_previous_working_day(valuation_date)
    print(f"📅 Trying previous working day: {ref_date}")

    data = fetch_bhavcopy_safe(fetcher, ref_date)

    # Step 2: If data exists → good
    if data is not None:
        print(f"✅ Bhavcopy found for {ref_date}")
        return ref_date, data

    # Step 3: If not found → fallback to earlier dates (skip weekends & holidays)
    print("⚠️ Bhavcopy not available for this date.")
    print("Looking for earlier available dates...")

    fallback = ref_date
    max_lookback_days = 30

    while (ref_date - fallback).days < max_lookback_days:
        fallback -= timedelta(days=1)
        
        # Skip weekends (5=Saturday, 6=Sunday)
        if fallback.weekday() in [5, 6]:
            print(f"⏭️  Skipping {fallback} (weekend)")
            continue
        
        # Skip holidays
        if is_market_holiday(fallback):
            print(f"⏭️  Skipping {fallback} (market holiday)")
            continue

        print(f"🔄 Checking {fallback}...")
        data = fetch_bhavcopy_safe(fetcher, fallback)
        
        if data is not None:
            print(f"✅ Using fallback date: {fallback}")
            return fallback, data

    # If nothing found within lookback period
    raise ValueError("❌ No bhavcopy found in the last 30 trading days.")


def weekly_atm_iv(weekly_options, spot_price, valuation_date, r=0):
    """
    Calculate ATM implied volatility from weekly options
    """
    atm_ce, atm_pe = get_atm_options(weekly_options, spot_price)

    expiry = atm_ce["XpryDt"].date()
    print(f"ATM Expiry: {expiry}")
    
    T = compute_ttm(valuation_date, expiry)

    iv_ce = implied_vol(
        atm_ce["ClsPric"], spot_price,
        atm_ce["StrkPric"], T, r, "CE"
    )

    iv_pe = implied_vol(
        atm_pe["ClsPric"], spot_price,
        atm_pe["StrkPric"], T, r, "PE"
    )

    atm_iv = (iv_ce + iv_pe) / 2 if (iv_ce and iv_pe) else 0.12

    return {
        "Expiry": expiry,
        "TTM": T,
        "ATM Strike": atm_ce["StrkPric"],
        "ATM IV": atm_iv
    }


def validate_atm_strike(user_legs, weekly_opts, spot_price):
    """
    Validate that the first leg is close to ATM (within reasonable range)
    Returns: (is_valid, distance_from_atm)
    """
    first_leg = user_legs[0]
    user_atm_strike = first_leg["strike"]
    
    # Get the actual ATM from options data
    atm_ce, atm_pe = get_atm_options(weekly_opts, spot_price)
    actual_atm = atm_ce["StrkPric"]
    
    distance = abs(user_atm_strike - actual_atm)
    
    # Allow up to ±1 strike away from computed ATM
    is_valid = distance <= 100  # typically 1 strike = 100 points for NIFTY
    
    print(f"[*] User-specified ATM strike: {user_atm_strike}")
    print(f"[*] Computed ATM strike:       {actual_atm}")
    print(f"[*] Distance:                  {distance} points")
    
    if is_valid:
        print(f"✅ ATM strike validation passed")
    else:
        print(f"⚠️  WARNING: First strike {user_atm_strike} is not very close to ATM {actual_atm}")
    
    return is_valid, distance



def get_dynamic_user_input():
    """
    Collect user inputs dynamically through interactive prompts
    Returns: Dictionary with valuation_date, risk_free_rate, bhavcopy_file, and legs
    """
    print("\n" + "=" * 60)
    print("STRATEGY PnL ANALYZER - USER INPUT")
    print("=" * 60 + "\n")

    # 1. Get Valuation Date
    while True:
        try:
            date_str = input("📅 Enter valuation date (YYYY-MM-DD): ").strip()
            valuation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Check if it's a trading day
            if is_market_holiday(valuation_date):
                print(f"❌ {valuation_date} is a market holiday. Please enter a trading day.")
                continue
            
            # Check if it's a weekend
            if valuation_date.weekday() in [5, 6]:
                print(f"❌ {valuation_date} is a weekend. Please enter a weekday.")
                continue
            
            print(f"✅ Valuation date set to: {valuation_date}")
            break
        except ValueError:
            print("❌ Invalid date format. Please use YYYY-MM-DD format.")

    # 2. Get Risk-Free Rate
    while True:
        try:
            rfr_str = input("\n📊 Enter Risk-Free Rate (as decimal, e.g., 0.05 for 5%): ").strip()
            risk_free_rate = float(rfr_str)
            
            if risk_free_rate < 0 or risk_free_rate > 1:
                print("❌ RFR should be between 0 and 1.")
                continue
            
            print(f"✅ Risk-Free Rate set to: {risk_free_rate * 100:.2f}%")
            break
        except ValueError:
            print("❌ Invalid input. Please enter a decimal number.")

    # 3. Ask about Bhavcopy File
    print("\n📁 Do you have a bhavcopy file to upload?")
    bhavcopy_file = None
    
    while True:
        choice = input("   (yes/no): ").strip().lower()
        
        if choice in ['yes', 'y']:
            file_path = input("   Enter the file path: ").strip()
            
            if os.path.exists(file_path):
                bhavcopy_file = file_path
                print(f"✅ Bhavcopy file: {file_path}")
                break
            else:
                print(f"❌ File not found: {file_path}")
        
        elif choice in ['no', 'n']:
            print("✅ Will fetch data from NSE automatically.")
            break
        
        else:
            print("❌ Please enter 'yes' or 'no'.")

    # 4. Get Number of Legs
    while True:
        try:
            num_legs_str = input("\n🔢 How many legs do you want to add? (1-10): ").strip()
            num_legs = int(num_legs_str)
            
            if num_legs < 1 or num_legs > 10:
                print("❌ Please enter a number between 1 and 10.")
                continue
            
            print(f"✅ Number of legs: {num_legs}")
            break
        except ValueError:
            print("❌ Invalid input. Please enter an integer.")

    # 5. Collect Leg Details
    legs = []
    valid_option_types = ['CE', 'PE']
    valid_sides = ['BUY', 'SELL']

    for leg_num in range(1, num_legs + 1):
        print(f"\n{'─' * 60}")
        print(f"LEG {leg_num}")
        if leg_num == 1:
            print(f"[ATM Strike - IV Reference]")
        else:
            print(f"[OTM Strike]")
        print(f"{'─' * 60}")

        # Strike Price
        while True:
            try:
                strike_str = input(f"   Strike Price: ").strip()
                strike = int(strike_str)
                
                if strike <= 0:
                    print("❌ Strike price must be positive.")
                    continue
                break
            except ValueError:
                print("❌ Invalid input. Please enter an integer.")

        # Option Type
        while True:
            opt_type = input(f"   Option Type (CE/PE): ").strip().upper()
            
            if opt_type not in valid_option_types:
                print(f"❌ Invalid option type. Please enter 'CE' or 'PE'.")
                continue
            break

        # Position/Side
        while True:
            side = input(f"   Position/Side (BUY/SELL): ").strip().upper()
            
            if side not in valid_sides:
                print(f"❌ Invalid side. Please enter 'BUY' or 'SELL'.")
                continue
            break

        # Quantity
        while True:
            try:
                qty_str = input(f"   Quantity: ").strip()
                qty = int(qty_str)
                
                if qty <= 0:
                    print("❌ Quantity must be positive.")
                    continue
                break
            except ValueError:
                print("❌ Invalid input. Please enter an integer.")

        legs.append({
            "strike": strike,
            "type": opt_type,
            "side": side,
            "qty": qty
        })
        
        print(f"✅ Leg {leg_num}: {side} {qty} {opt_type} {strike}")

    print("\n" + "=" * 60)
    print("INPUT SUMMARY")
    print("=" * 60)
    print(f"Valuation Date: {valuation_date}")
    print(f"Risk-Free Rate: {risk_free_rate * 100:.2f}%")
    print(f"Bhavcopy File: {'Yes' if bhavcopy_file else 'Auto-fetch from NSE'}")
    print(f"Number of Legs: {num_legs}")
    for i, leg in enumerate(legs, 1):
        print(f"  Leg {i}: {leg['side']} {leg['qty']} {leg['type']} {leg['strike']}")
    print("=" * 60 + "\n")

    return {
        "valuation_date": valuation_date,
        "risk_free_rate": risk_free_rate,
        "bhavcopy_file": bhavcopy_file,
        "legs": legs
    }


def main():
    # --- 1. User Inputs (Hardcoded) ---
    user_input = {
        "valuation_date": date(2026, 1, 29),
        "risk_free_rate": 0.00,
        "bhavcopy_file": None,  # Set to file path if user has bhavcopy data
        "legs": [
            {
                "strike": 25300,
                "type": "PE",
                "side": "BUY",
                "qty": 1950
            },
            {
                "strike": 25050,
                "type": "PE",
                "side": "SELL",
                "qty": 3900
            }
        ]
    }

    symbol = "NIFTY"
    valuation_date = user_input["valuation_date"]

    # Validate date
    if is_market_holiday(valuation_date):
        print(f"❌ ERROR: {valuation_date} is a market holiday.")
        print("Please enter a valid trading date and try again.")
        sys.exit(1)

    # --- 2. Load or Fetch Data ---
    try:
        print(f"[*] Fetching data for IV calculation...")
        
        if user_input["bhavcopy_file"]:
            # USER PROVIDED BHAVCOPY FILE
            print("[*] Using user-provided bhavcopy data...")
            bhavcopy_data = load_user_bhavcopy(user_input["bhavcopy_file"])
            
            if bhavcopy_data is None:
                raise ValueError("Failed to load user bhavcopy file")
            
            # Validate bhavcopy data against valuation date
            validate_bhavcopy_data(bhavcopy_data, valuation_date)
            
            # Extract weekly options from bhavcopy
            weekly_opts = extract_weekly_options_from_bhavcopy(bhavcopy_data, symbol)
            if weekly_opts is None or weekly_opts.empty:
                raise ValueError("No weekly options found in bhavcopy")
            
            # Extract spot price from futures
            spot_price = extract_spot_price_from_futures(bhavcopy_data, symbol)
            if spot_price is None:
                raise ValueError("Could not extract spot price from futures data")
            
            iv_ref_date = valuation_date
        
        else:
            # AUTO-FETCH DATA (CURRENT LOGIC)
            print("[*] Auto-fetching data from NSE...")
            iv_ref_date, weekly_opts = get_iv_reference_date(symbol, valuation_date)
            
            # Get spot price from the IV reference date
            spot_price = DataFetcher.fetch_spot_price(symbol, iv_ref_date)
        
        print(f"[*] Spot Price: {spot_price}")
        print(f"[*] Fetched {len(weekly_opts)} weekly options contracts")
        print(f"[*] Weekly expiry: {weekly_opts['XpryDt'].iloc[0]}")

    except Exception as e:
        print(f"CRITICAL ERROR fetching data: {e}")
        sys.exit(1)

    # --- 3. Calculate ATM Implied Volatility from First Leg (User Input) ---
    try:
        print("[*] Calculating ATM Implied Volatility...")
        
        # Validate that the first leg is the ATM strike
        print("[*] Validating user-specified ATM strike...")
        validate_atm_strike(user_input["legs"], weekly_opts, spot_price)
        
        # Get ATM strike from first leg (user input)
        atm_strike_from_user = user_input["legs"][0]["strike"]
        atm_option_type = user_input["legs"][0]["type"]
        
        print(f"[*] Using ATM Strike from user input: {atm_strike_from_user} ({atm_option_type})")
        
        # Get the ATM option from weekly options data to calculate IV
        atm_option = weekly_opts[
            (weekly_opts["StrkPric"] == atm_strike_from_user) &
            (weekly_opts["OptnTp"] == atm_option_type)
        ]
        
        if atm_option.empty:
            print(f"⚠️ WARNING: ATM strike {atm_strike_from_user} {atm_option_type} not found in options data.")
            print("Falling back to automatic ATM detection...")
            iv_result = weekly_atm_iv(weekly_opts, spot_price, iv_ref_date, user_input["risk_free_rate"])
            atm_strike_from_user = iv_result['ATM Strike']
        else:
            atm_option = atm_option.iloc[0]
            expiry = pd.to_datetime(atm_option["XpryDt"])
            T = compute_ttm(iv_ref_date, expiry.date())
            
            # Calculate IV for the user-specified ATM strike
            atm_iv = implied_vol(
                atm_option["ClsPric"], spot_price,
                atm_strike_from_user, T, user_input["risk_free_rate"], atm_option_type
            )
            
            if atm_iv is None:
                atm_iv = 0.12
            
            iv_result = {
                "Expiry": expiry,
                "TTM": T,
                "ATM Strike": atm_strike_from_user,
                "ATM IV": atm_iv
            }
        
        expiry = pd.to_datetime(iv_result["Expiry"])
        atm_iv = iv_result["ATM IV"]
        
        print(f"[*] ATM Strike: {iv_result['ATM Strike']}")
        print(f"[*] ATM IV: {atm_iv:.4f}")
        print(f"[*] Time to Expiry: {iv_result['TTM']:.4f} years")

    except Exception as e:
        print(f"ERROR calculating IV: {e}")
        sys.exit(1)

    # --- 4. Attach Premiums from Bhavcopy ---
    try:
        print("[*] Attaching market premiums to legs...")
        
        legs_with_premium, skipped_legs = attach_premiums_from_bhavcopy(
            user_input["legs"],
            weekly_opts
        )

        print(f"[*] Valid legs: {len(legs_with_premium)}")
        for leg in legs_with_premium:
            print(f"   {leg['type']} {leg['strike']} @ {leg['premium']} - {leg['side']} {leg['qty']}")

        if skipped_legs:
            print(f"⚠️ Skipped legs: {len(skipped_legs)}")
            for leg in skipped_legs:
                print(f"   {leg['type']} {leg['strike']}")

    except Exception as e:
        print(f"CRITICAL ERROR attaching premiums: {e}")
        sys.exit(1)

    # --- 5. Calculate PnL Curve ---
    try:
        print("[*] Calculating PnL curve...")
        
        S0 = spot_price
        T = iv_result["TTM"]  # Use the TTM already calculated (accounts for holidays, weekends, etc)
        sigma = atm_iv
        
        print(f"[*] Using constant IV assumption: {sigma:.4f} (from ATM strike {iv_result['ATM Strike']})")
        print(f"[*] IV applied to all legs in the strategy")

        spots, pnls = pnl_curve(S0, legs_with_premium, T, sigma, user_input["risk_free_rate"])

        exp_pnl, prob_profit = expected_metrics(spots, pnls, S0, sigma, T)

        print("\n" + "=" * 60)
        print("STRATEGY ANALYSIS")
        print("=" * 60)
        # print(f"Expected PnL:          ₹ {round(exp_pnl, 2)}")
        print(f"Probability of Profit: {round(prob_profit * 100, 2)}%")
        print(f"Max Profit:            ₹ {round(max(pnls), 2)}")
        # print(f"Max Loss:              ₹ {round(min(pnls), 2)}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"ERROR calculating PnL curve: {e}")
        sys.exit(1)

    # --- 6. Plot PnL Curve ---
    try:
        print("[*] Plotting PnL curve...")
        Visualizer.plot_pnl_curve(spots, pnls)
    except Exception as e:
        print(f"ERROR plotting PnL curve: {e}")

    # --- 7. Plot PnL Evolution ---
    try:
        print("[*] Plotting PnL evolution over time...")
        Visualizer.plot_pnl_evolution(
            positions=legs_with_premium,
            spot_price=spot_price,
            valuation_date=valuation_date,
            expiry_date=expiry.date(),
            iv=atm_iv,
            risk_free_rate=user_input["risk_free_rate"]
        )
    except Exception as e:
        print(f"ERROR plotting PnL evolution: {e}")


if __name__ == "__main__":
    main()
