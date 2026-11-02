"""
24/7 Dedicated Cloud Background Worker for Solana Quant Swap Terminal.
Runs an autonomous infinite tick loop independent of the browser or local PC.
Can be hosted on any cloud server, VPS, Render, Railway, or run as a background service.
"""

import time
import sys
import os

# Add root directory to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.demo_engine import load_demo_state, save_demo_state, evaluate_demo_tick
from backend.main import get_pairs_rotation, fetch_jup_prices, TOKEN_MINTS

def run_247_worker(poll_interval_sec: float = 3.0):
    print("=" * 60)
    print("🚀 Solana Quant Terminal: 24/7 Pure Shannon Background Daemon Started")
    print(f"⏱️ Polling live Jupiter DEX orderbook every {poll_interval_sec}s...")
    print("=" * 60)

    consecutive_errors = 0
    while True:
        try:
            state = load_demo_state()
            if not state.get("is_running", True):
                time.sleep(poll_interval_sec)
                continue

            # 1. Fetch live Jupiter price matrix
            pairs_data = get_pairs_rotation()
            sol_prices = fetch_jup_prices([TOKEN_MINTS["SOL"]])
            sol_usd = sol_prices.get(TOKEN_MINTS["SOL"], {}).get("usdPrice", 95.0)

            # 2. Evaluate Pure Shannon 50/50 tick
            prev_cycles = state.get("total_cycles_completed", 0)
            new_state = evaluate_demo_tick(pairs_data, sol_usd, client_state=state)
            new_cycles = new_state.get("total_cycles_completed", 0)

            # Log rebalance triggers immediately
            if new_cycles > prev_cycles:
                latest = new_state.get("trade_history", [{}])[0]
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚡ REBALANCE TRIGGERED: {latest.get('action')}")
                print(f"   Net Gain: {latest.get('net_profit_sol')} SOL | Total Alpha: {new_state.get('total_harvested_alpha_sol')} SOL")

            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors <= 3:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ Worker Warning: {e}")
            time.sleep(5.0)

        time.sleep(poll_interval_sec)

if __name__ == "__main__":
    run_247_worker(poll_interval_sec=3.0)
