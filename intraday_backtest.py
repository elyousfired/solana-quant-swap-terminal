"""
Intraday Backtesting Analysis (15m & 1h candles)
Analyzes exact frequency of opportunities per day across Solana pairs.
"""

import urllib.request
import json
import numpy as np

def fetch_klines(sym, interval="15m", limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return np.array([float(c[4]) for c in raw])

def run():
    print("=" * 65)
    print("INTRADAY SOLANA QUANT OPPORTUNITY FREQUENCY ANALYSIS")
    print("=" * 65)

    # 1. 15-minute candles (~10.4 days of intraday action)
    sol_15m = fetch_klines("SOLUSDT", "15m", 1000)
    jup_15m = fetch_klines("JUPUSDT", "15m", 1000)
    ray_15m = fetch_klines("RAYUSDT", "15m", 1000)
    jto_15m = fetch_klines("JTOUSDT", "15m", 1000)
    usdc_15m = np.ones_like(sol_15m)

    days_15m = len(sol_15m) * 15 / (60 * 24)

    from backtest_engine import backtest_shannon_demon, backtest_pairs_rotation

    pairs = [
        ("SOL", "JUP", sol_15m, jup_15m),
        ("SOL", "RAY", sol_15m, ray_15m),
        ("SOL", "JTO", sol_15m, jto_15m),
        ("SOL", "USDC", sol_15m, usdc_15m)
    ]

    print(f"\n[A] SHANNON'S DEMON 50/50 REBALANCING (Intraday 15m Candles over {days_15m:.1f} Days):")
    print(f"{'Pair':<10} | {'Band %':<7} | {'Total Swaps':<12} | {'Opps / Day':<12} | {'Hours/Swap':<12} | {'Net Alpha'}")
    print("-" * 68)

    total_daily_shannon_opps = 0.0

    for name_a, name_b, pa, pb in pairs:
        for band in [1.5, 2.0]:
            res = backtest_shannon_demon(pa, pb, name_a, name_b, band_pct=band, fee_pct=0.10)
            if band == 2.0:
                total_daily_shannon_opps += res['opportunities_per_day']
            print(f"{res['pair']:<10} | {band:<7.1f}% | {res['total_opportunities']:<12} | {res['opportunities_per_day']:<12.2f} | {res['avg_hours_between']:<12.1f}h | +{res['harvested_alpha_pct']}%")

    print(f"\n>> Total Shannon Opportunities across all monitored pairs: ~{total_daily_shannon_opps:.1f} to {total_daily_shannon_opps * 1.5:.1f} opportunities per day!")

    print("\n" + "=" * 65)
    print("[B] STATISTICAL PAIRS ROTATION (Z-Score >= 2.0 Mean Reversion):")
    print(f"{'Pair':<10} | {'Cycles':<8} | {'Cycles / Day':<14} | {'Cycles / Week':<14} | {'Avg Yield/Cycle'}")
    print("-" * 68)

    total_daily_rot_opps = 0.0
    rot_pairs = [
        ("JUP", "SOL", jup_15m, sol_15m),
        ("RAY", "SOL", ray_15m, sol_15m),
        ("JTO", "SOL", jto_15m, sol_15m)
    ]
    for nb, nq, pb, pq in rot_pairs:
        # window 96 15m candles = 24h rolling lookback
        res = backtest_pairs_rotation(pb, pq, nb, nq, window=96, z_threshold=2.0)
        total_daily_rot_opps += res['cycles_per_day']
        print(f"{res['pair']:<10} | {res['completed_cycles']:<8} | {res['cycles_per_day']:<14.2f} | {res['cycles_per_week']:<14.2f} | +{res['avg_token_gain_per_cycle']}%")

    print(f"\n>> Total Statistical Rotation Cycles across pairs: ~{total_daily_rot_opps:.2f} per day (~{total_daily_rot_opps * 7:.1f} per week)!")

    # Summary table for the user
    summary_data = {
        "days_tested": round(days_15m, 1),
        "shannon_total_opps_day": round(total_daily_shannon_opps, 2),
        "rotation_total_opps_day": round(total_daily_rot_opps, 2),
    }
    with open("intraday_summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)

if __name__ == "__main__":
    run()
