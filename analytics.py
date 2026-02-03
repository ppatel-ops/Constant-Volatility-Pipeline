import numpy as np
from scipy.stats import norm
from math import log, sqrt, exp
from datetime import timedelta
from fetcher import get_nse_holidays


class BlackScholes:
    @staticmethod
    def price(S, K, T, r, sigma, option_type='CE'):
        """
        S: Spot Price
        K: Strike Price
        T: Time to Expiry (years)
        r: Risk-free rate
        sigma: Implied Volatility
        option_type: 'CE' or 'PE'
        """
        if T <= 1e-5:  # Expiry
            return max(0, S - K) if option_type == 'CE' else max(0, K - S)

        d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)

        if option_type == 'CE':
            return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
        else:
            return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    @staticmethod
    def vega(S, K, T, r, sigma):
        """
        Calculate vega for an option
        """
        d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
        return S * norm.pdf(d1) * sqrt(T)


def forward_price(spot, r, T):
    """Calculate forward price"""
    return spot * exp(r * T)


def bs_price(S, K, T, r, sigma, option_type):
    """
    Black-Scholes price calculation
    """
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)

    if option_type == "CE":
        return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    else:
        return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_vega(S, K, T, r, sigma):
    """
    Calculate vega for an option
    """
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    return S * norm.pdf(d1) * sqrt(T)


def implied_vol(market_price, S, K, T, r, option_type, tol=1e-6, max_iter=1000):
    """
    Calculate implied volatility using Newton-Raphson method
    """
    if market_price < 0.5:
        return None

    sigma = 0.2  # initial guess

    for _ in range(max_iter):
        price = bs_price(S, K, T, r, sigma, option_type)
        vega = bs_vega(S, K, T, r, sigma)

        if vega < 1e-8:
            break

        diff = price - market_price
        if abs(diff) < tol:
            return sigma

        sigma -= diff / vega

        # Clamp sigma to sane range
        sigma = max(0.01, min(sigma, 3.0))

    return sigma


TRADING_TIME = 0.75
NON_TRADING_TIME = 0.25


def compute_ttm(valuation_date, expiry_date):
    """
    Compute time to maturity accounting for trading/non-trading hours and NSE holidays
    Returns time to maturity as a fraction of a year
    """
    if valuation_date >= expiry_date:
        return 0.0

    ttm_days = 0.0
    d = valuation_date + timedelta(days=1)

    # Count full days between valuation date and expiry
    while d < expiry_date:
        # Check if it's a weekend or NSE holiday
        is_weekend = d.weekday() >= 5  # Saturday=5, Sunday=6
        year = d.year
        nse_holidays = get_nse_holidays(year)
        is_holiday = d.strftime("%Y-%m-%d") in nse_holidays
        
        if is_weekend or is_holiday:
            ttm_days += NON_TRADING_TIME  # 0.25 for non-trading days
        else:
            ttm_days += 1.0  # full trading day
        d += timedelta(days=1)

    # Add expiry day contribution (0.75 for trading hours at expiry)
    ttm_open = ttm_days + TRADING_TIME

    return ttm_open / 365