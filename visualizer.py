import matplotlib.pyplot as plt
import numpy as np


class Visualizer:
    @staticmethod
    def plot_strategy(spot_range, data_dict, current_spot, entry_date, expiry_date):
        """Plot strategy payoff at different times to expiry"""
        plt.figure(figsize=(12, 7))

        for plot_date, pnl_values in data_dict.items():
            days_remaining = (expiry_date - plot_date).days
            
            if days_remaining == 0:
                plt.plot(spot_range, pnl_values, label="Expiry (Maturity)", color='black', linewidth=2.5)
            elif plot_date.date() == entry_date.date():
                plt.plot(spot_range, pnl_values, label="Entry (Today)", color='blue', linestyle='--')
            else:
                plt.plot(spot_range, pnl_values, label=f"T-{days_remaining} Days", alpha=0.6)

        plt.axhline(0, color='red', linewidth=1)
        plt.axvline(current_spot, color='gray', linestyle=':', label=f"Spot {current_spot}")
        
        plt.title(f"Strategy Payoff: {entry_date.date()} to {expiry_date.date()}")
        plt.xlabel("Underlying Spot Price")
        plt.ylabel("PnL")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()

    @staticmethod
    def plot_pnl_curve(spots, pnls):
        """Plot the PnL curve across spot prices"""
        plt.figure(figsize=(10, 5))

        plt.plot(spots, pnls, label="PnL Curve", color="blue")
        plt.axhline(0, color="black", linestyle="--", linewidth=1)
        plt.axvline(spots[len(spots)//2], color="gray", linestyle="--", alpha=0.5)

        plt.title("PnL Curve")
        plt.xlabel("Underlying Price")
        plt.ylabel("Profit / Loss")
        plt.grid(True)
        plt.legend()

        plt.show()

    @staticmethod
    def plot_pnl_evolution(
        positions,
        spot_price,
        valuation_date,
        expiry_date,
        iv,
        risk_free_rate=0.0,
        n_spot_points=120,
        n_time_slices=5
    ):
        """Plot PnL evolution over time as spot price changes"""
        from strategy import strategy_pnl

        TRADING_DAY_FRACTION = 0.75

        # Spot range
        spot_range = np.linspace(
            spot_price * 0.95,
            spot_price * 1.05,
            n_spot_points
        )

        # Time slices
        from datetime import timedelta
        total_days = (expiry_date - valuation_date).days
        time_points = np.linspace(0, total_days, n_time_slices).astype(int)

        plt.figure(figsize=(12, 7))

        for t in time_points:
            current_date = valuation_date + timedelta(days=int(t))
            remaining_days = (expiry_date - current_date).days

            T = max((remaining_days * TRADING_DAY_FRACTION) / 365, 1e-6)

            pnl_curve = [
                strategy_pnl(S, positions, T, iv, risk_free_rate)
                for S in spot_range
            ]

            if remaining_days == 0:
                plt.plot(spot_range, pnl_curve, label="Expiry", linewidth=3, color="black")
            elif t == 0:
                plt.plot(spot_range, pnl_curve, label="Today", linestyle="--", color="blue")
            else:
                plt.plot(spot_range, pnl_curve, label=f"T-{remaining_days} days", alpha=0.7)

        plt.axhline(0, color="red", linestyle="--")
        plt.axvline(spot_price, color="gray", linestyle=":")
        plt.title("PnL Evolution Over Time")
        plt.xlabel("Underlying Price")
        plt.ylabel("PnL")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()