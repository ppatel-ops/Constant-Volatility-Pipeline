import numpy as np
import pandas as pd
from datetime import timedelta
from scipy.stats import norm
from analytics import bs_price


def get_atm_options(options_df: pd.DataFrame, spot_price: float):
    """
    Get ATM (At-The-Money) call and put options
    """
    options_df = options_df.copy()
    options_df["dist"] = abs(options_df["StrkPric"] - spot_price)

    atm_ce = options_df[options_df["OptnTp"] == "CE"].sort_values("dist").iloc[0]
    atm_pe = options_df[options_df["OptnTp"] == "PE"].sort_values("dist").iloc[0]
    
    return atm_ce, atm_pe


def attach_premiums_from_bhavcopy(legs, options_df):
    """
    Attach market premiums from bhavcopy to legs
    """
    enriched = []
    skipped = []

    for leg in legs:
        row = options_df[
            (options_df["StrkPric"] == leg["strike"]) &
            (options_df["OptnTp"] == leg["type"])
        ]

        if row.empty:
            print(
                f"⚠️ WARNING: No option found for "
                f"{leg['type']} {leg['strike']} — skipping this leg."
            )
            skipped.append(leg)
            continue

        premium = float(row.iloc[0]["ClsPric"])

        enriched.append({
            **leg,
            "premium": premium
        })

    if not enriched:
        raise ValueError("❌ No valid option legs found. Cannot proceed.")

    return enriched, skipped


def option_pnl(S, leg, T, sigma, r=0):
    """
    Calculate PnL for a single option leg at spot price S
    """
    price_now = bs_price(
        S,
        leg["strike"],
        T,
        r,
        sigma,
        leg["type"]
    )

    pnl = price_now - leg["premium"]

    if leg["side"] == "SELL":
        pnl = -pnl

    return pnl * leg["qty"]


def strategy_pnl(S, legs, T, sigma, r=0):
    """
    Calculate total strategy PnL for all legs at spot price S
    """
    total = 0
    for leg in legs:
        total += option_pnl(S, leg, T, sigma, r)
    return total


def pnl_curve(S0, legs, T, sigma, r=0):
    """
    Generate PnL curve across a range of spot prices
    """
    spots = np.linspace(0.7 * S0, 1.3 * S0, 1500)
    pnls = [strategy_pnl(s, legs, T, sigma, r) for s in spots]
    return spots, pnls


def spot_pdf(S, S0, sigma, T):
    """
    Probability density function for spot price (lognormal distribution)
    """
    mu = np.log(S0) - 0.5 * sigma ** 2 * T
    return norm.pdf(np.log(S), mu, sigma * np.sqrt(T)) / S


def expected_metrics(spots, pnls, S0, sigma, T):
    """
    Calculate expected PnL and probability of profit
    """
    spots = np.array(spots)
    pnls = np.array(pnls)

    # Probability density
    probs = spot_pdf(spots, S0, sigma, T)

    # Expected PnL
    expected_pnl = np.trapezoid(pnls * probs, spots)

    # Probability of profit
    profit_mask = pnls > 0
    prob_profit = np.trapezoid(probs[profit_mask], spots[profit_mask])

    return expected_pnl, prob_profit


# def expected_metrics(spots, pnls, S0, sigma, T):
#     """
#     Calculate expected PnL and probability of profit
#     """
#     spots = np.array(spots)
#     pnls = np.array(pnls)
#
#     # Probability density
#     probs = spot_pdf(spots, S0, sigma, T)
#
#     # Expected PnL
#     expected_pnl = np.trapezoid(pnls * probs, spots)
#
#     # Probability of profit
#     profit_mask = pnls > 0
#     prob_profit = np.trapezoid(probs[profit_mask], spots[profit_mask])
#
#     return expected_pnl, prob_profit


class StrategyManager:
    def __init__(self, positions, spot_price, date_entry, date_expiry, iv, r):
        self.positions = positions
        self.spot_price = spot_price
        self.date_entry = date_entry
        self.date_expiry = date_expiry
        self.iv = iv
        self.r = r
        self.TRADING_DAY_FRACTION = 0.75

    def generate_payoff_matrix(self):
        """
        Generates PnL values for:
        1. A range of Spot Prices (X-axis)
        2. Multiple time steps (Curves)
        """
        # Range: +/- 5% of spot
        spot_range = np.linspace(self.spot_price * 0.95, self.spot_price * 1.05, 100)
        
        # Time steps: 5 intervals between now and expiry
        total_days = (self.date_expiry - self.date_entry).days
        if total_days < 1:
            total_days = 1
        
        dates_to_plot = [self.date_entry + timedelta(days=int(i)) for i in np.linspace(0, total_days, 5)]
        
        # Ensure exact expiry is included
        if dates_to_plot[-1] != self.date_expiry:
            dates_to_plot[-1] = self.date_expiry

        results = {}

        for plot_date in dates_to_plot:
            days_remaining = (self.date_expiry - plot_date).days
            T = max((days_remaining * self.TRADING_DAY_FRACTION) / 365.0, 1e-6)
            
            pnl_values = []
            
            for S in spot_range:
                total_pnl = strategy_pnl(S, self.positions, T, self.iv, self.r)
                pnl_values.append(total_pnl)
            
            results[plot_date] = pnl_values

        return spot_range, results