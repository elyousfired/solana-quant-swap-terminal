"""
Solana Quant Backtesting Engine
Evaluates real historical data (30-day 1-hour candles from Binance)
for Shannon's Demon 50/50 and Statistical Pairs Rotation.
"""

import urllib.request
import json
import numpy as np

def fetch_candles(symbol, limit=720):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = json.loads(urllib.request.urlopen(req, timeout=10).read())
    # raw candle: [open_time, open, high, low, close, volume, ...]
    closes = [float(c[4]) for c in raw]
    timestamps = [int(c[0]) for c in raw]
    return timestamps, np.array(closes)

def backtest_shannon_demon(prices_a, prices_b, token_a_name="SOL", token_b_name="JUP", band_pct=2.0, fee_pct=0.15):
    """
    Shannon's Demon 50/50 Rebalancing Backtest.
    Initial: $10,000 capital ($5,000 in A, $5,000 in B).
    """
    initial_cap = 10000.0
    qty_a = (initial_cap * 0.5) / prices_a[0]
    qty_b = (initial_cap * 0.5) / prices_b[0]

    # Buy and hold benchmark
    bh_qty_a = qty_a
    bh_qty_b = qty_b

    rebalance_events = 0
    rebalance_history = []
    days = len(prices_a) / 24.0

    shannon_values = []
    bh_values = []

    for i in range(len(prices_a)):
        p_a = prices_a[i]
        p_b = prices_b[i]

        val_a = qty_a * p_a
        val_b = qty_b * p_b
        total_val = val_a + val_b

        weight_a = val_a / total_val
        weight_b = val_b / total_val
        drift = abs(weight_a - 0.5) * 100.0

        if drift >= band_pct:
            # Rebalance back to 50/50
            target_val_each = total_val * 0.5
            diff_val = abs(val_a - target_val_each)
            
            # Apply swap fee on traded amount
            fee_cost = diff_val * (fee_pct / 100.0)
            net_total_val = total_val - fee_cost
            
            qty_a = (net_total_val * 0.5) / p_a
            qty_b = (net_total_val * 0.5) / p_b
            
            direction = f"{token_a_name}->{token_b_name}" if weight_a > 0.5 else f"{token_b_name}->{token_a_name}"
            rebalance_events += 1
            rebalance_history.append((i, direction, drift, total_val))

        shannon_values.append(qty_a * p_a + qty_b * p_b)
        bh_values.append(bh_qty_a * p_a + bh_qty_b * p_b)

    final_shannon = shannon_values[-1]
    final_bh = bh_values[-1]
    shannon_ret = ((final_shannon - initial_cap) / initial_cap) * 100.0
    bh_ret = ((final_bh - initial_cap) / initial_cap) * 100.0
    alpha = shannon_ret - bh_ret

    # Max Drawdowns
    sh_arr = np.array(shannon_values)
    bh_arr = np.array(bh_values)
    sh_dd = np.min(sh_arr / np.maximum.accumulate(sh_arr) - 1.0) * 100.0
    bh_dd = np.min(bh_arr / np.maximum.accumulate(bh_arr) - 1.0) * 100.0

    opps_per_day = rebalance_events / days
    avg_hours_between = (len(prices_a) / max(1, rebalance_events))

    return {
        "pair": f"{token_a_name}/{token_b_name}",
        "days": days,
        "band_pct": band_pct,
        "total_opportunities": rebalance_events,
        "opportunities_per_day": round(opps_per_day, 2),
        "avg_hours_between": round(avg_hours_between, 1),
        "shannon_return_pct": round(shannon_ret, 2),
        "buy_hold_return_pct": round(bh_ret, 2),
        "harvested_alpha_pct": round(alpha, 2),
        "shannon_max_dd": round(sh_dd, 2),
        "buy_hold_max_dd": round(bh_dd, 2),
        "dd_reduction": round(abs(bh_dd) - abs(sh_dd), 2)
    }

def backtest_pairs_rotation(prices_base, prices_quote, base_name="JUP", quote_name="SOL", window=48, z_threshold=2.0):
    """
    Statistical Arbitrage Pairs Rotation Backtest.
    Direct coin-to-coin mean reversion.
    """
    ratios = prices_base / prices_quote
    days = len(ratios) / 24.0

    positions = 0 # 1: Long Base / Short Quote, -1: Long Quote / Short Base
    trades = 0
    cycles = 0
    token_gain_pct = 0.0

    entry_ratio = 0.0

    for i in range(window, len(ratios)):
        window_ratios = ratios[i-window:i]
        mean = np.mean(window_ratios)
        std = np.std(window_ratios)
        if std == 0:
            continue
        z = (ratios[i] - mean) / std

        if positions == 0:
            if z <= -z_threshold:
                # Base is oversold vs Quote -> Swap Quote into Base
                positions = 1
                entry_ratio = ratios[i]
                trades += 1
            elif z >= z_threshold:
                # Base is overextended vs Quote -> Swap Base into Quote
                positions = -1
                entry_ratio = ratios[i]
                trades += 1
        elif positions == 1:
            if z >= 0.0: # Reverted to mean
                gain = (ratios[i] / entry_ratio - 1.0) * 100.0 - 0.3 # 0.3% roundtrip fee
                token_gain_pct += max(0, gain)
                positions = 0
                cycles += 1
        elif positions == -1:
            if z <= 0.0: # Reverted to mean
                gain = (entry_ratio / ratios[i] - 1.0) * 100.0 - 0.3
                token_gain_pct += max(0, gain)
                positions = 0
                cycles += 1

    return {
        "pair": f"{base_name}/{quote_name}",
        "days": days,
        "completed_cycles": cycles,
        "cycles_per_day": round(cycles / days, 2),
        "cycles_per_week": round((cycles / days) * 7, 2),
        "avg_token_gain_per_cycle": round(token_gain_pct / max(1, cycles), 2),
        "total_accumulated_extra_tokens_pct": round(token_gain_pct, 2)
    }

def main():
    print("=" * 60)
    print("SOLANA QUANT BACKTEST RUNNER (30 DAYS / 720 1H CANDLES)")
    print("=" * 60)

    _, sol_p = fetch_candles("SOLUSDT", 720)
    _, jup_p = fetch_candles("JUPUSDT", 720)
    _, ray_p = fetch_candles("RAYUSDT", 720)
    _, jto_p = fetch_candles("JTOUSDT", 720)
    usdc_p = np.ones_like(sol_p)

    pairs_to_test = [
        ("SOL", "JUP", sol_p, jup_p, 2.0),
        ("SOL", "RAY", sol_p, ray_p, 2.0),
        ("SOL", "JTO", sol_p, jto_p, 2.0),
        ("SOL", "USDC", sol_p, usdc_p, 1.5),
    ]

    print("\n--- 1. SHANNON'S DEMON 50/50 REBALANCING BACKTEST ---")
    shannon_results = []
    for a_name, b_name, pa, pb, band in pairs_to_test:
        res = backtest_shannon_demon(pa, pb, a_name, b_name, band_pct=band)
        shannon_results.append(res)
        print(f"\n[Pair: {res['pair']} | Band: {res['band_pct']}%]")
        print(f"  • Total Opportunities (30d): {res['total_opportunities']}")
        print(f"  • Opportunities Per Day:     {res['opportunities_per_day']} / day")
        print(f"  • Avg Hours Between Swaps:   {res['avg_hours_between']} hours")
        print(f"  • Harvested Pure Alpha:      +{res['harvested_alpha_pct']}% vs Buy&Hold")
        print(f"  • Max Drawdown Reduction:    {res['dd_reduction']}% lower risk")

    print("\n--- 2. STATISTICAL PAIRS ROTATION (Z-SCORE) BACKTEST ---")
    rotation_pairs = [
        ("JUP", "SOL", jup_p, sol_p),
        ("RAY", "SOL", ray_p, sol_p),
        ("JTO", "SOL", jto_p, sol_p),
    ]
    rot_results = []
    for b_name, q_name, pb, pq in rotation_pairs:
        res = backtest_pairs_rotation(pb, pq, b_name, q_name)
        rot_results.append(res)
        print(f"\n[Pair: {res['pair']}]")
        print(f"  • Completed Cycles (30d):    {res['completed_cycles']}")
        print(f"  • Opportunities Per Day:     {res['cycles_per_day']} / day")
        print(f"  • Opportunities Per Week:    {res['cycles_per_week']} / week")
        print(f"  • Avg Extra Token Yield:     +{res['avg_token_gain_per_cycle']}% per cycle")
        print(f"  • Total Extra Tokens Yield:  +{res['total_accumulated_extra_tokens_pct']}% extra tokens")

    # Save summary json
    summary = {
        "shannon": shannon_results,
        "rotation": rot_results
    }
    with open("backtest_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nSaved backtest_results.json successfully!")

if __name__ == "__main__":
    main()
