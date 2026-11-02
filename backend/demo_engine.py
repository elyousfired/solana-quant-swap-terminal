"""
Solana Quant Swap Terminal - Autonomous Paper Trading Demo Engine
Simulates automated 1.0 SOL quantitative swap execution on Solana leaders via Jupiter.
Features:
- Fixed 1.0 SOL initial capital
- Maximum 2 concurrent active swaps (Tranche allocation: max 0.45 SOL per position)
- Z-Score & Half-Life Mean Reversion strategy triggers
- Persistent state (Server file /tmp fallback + client localStorage sync)
- Autonomous offline Catch-Up: reconciles trades that occurred while user PC was off.
"""

import os
import json
import time
import math
from typing import Dict, Any, List

STATE_FILE_LOCAL = os.path.join(os.path.dirname(__file__), "demo_state.json")
STATE_FILE_TMP = "/tmp/demo_state.json"

def get_state_file_path() -> str:
    # Use local directory if writable, else /tmp for Vercel serverless
    try:
        test_file = STATE_FILE_LOCAL + ".test"
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return STATE_FILE_LOCAL
    except Exception:
        return STATE_FILE_TMP

def get_initial_state() -> Dict[str, Any]:
    return {
        "is_running": False,
        "initial_capital_sol": 1.0,
        "current_balance_sol": 1.0,
        "available_sol": 1.0,
        "total_profit_sol": 0.0,
        "total_profit_pct": 0.0,
        "max_concurrent_positions": 2,
        "active_positions": [],
        "trade_history": [],
        "last_tick_time": time.time(),
        "created_at": time.time()
    }

def load_demo_state() -> Dict[str, Any]:
    path = get_state_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass
    state = get_initial_state()
    save_demo_state(state)
    return state

def save_demo_state(state: Dict[str, Any]):
    path = get_state_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print("Error saving demo state:", e)

def reset_demo_state(client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    state = get_initial_state()
    state["is_running"] = True # Start running immediately upon reset
    save_demo_state(state)
    return state

def toggle_demo_state(running: bool = None, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    if client_state and isinstance(client_state, dict) and client_state.get("initial_capital_sol"):
        state = client_state
    else:
        state = load_demo_state()
    if running is None:
        state["is_running"] = not state.get("is_running", False)
    else:
        state["is_running"] = running
    state["last_tick_time"] = time.time()
    save_demo_state(state)
    return state

def sync_demo_state(client_state: Dict[str, Any]) -> Dict[str, Any]:
    """Syncs state from client localStorage if server was cold-started and state is fresh."""
    server_state = load_demo_state()
    if not server_state.get("trade_history") and client_state and client_state.get("trade_history"):
        save_demo_state(client_state)
        return client_state
    return server_state

def evaluate_demo_tick(live_pairs: List[Dict[str, Any]], sol_usd: float, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Main evaluation tick:
    1. Reconciles open positions against live ratios (closes if mean-reversion target reached).
    2. Opens new positions if active positions < 2 and a pair meets Z <= -2.0 sigma.
    3. Handles offline catch-up if user was away / PC was off.
    4. Updates balances, PnL, and persists state.
    """
    if client_state and isinstance(client_state, dict) and client_state.get("initial_capital_sol"):
        state = client_state
    else:
        state = load_demo_state()

    if not state.get("is_running", False):
        return state

    now = time.time()
    last_tick = float(state.get("last_tick_time", now))
    time_offline = max(0.0, now - last_tick)
    state["last_tick_time"] = now

    active_positions = state.get("active_positions", [])
    trade_history = state.get("trade_history", [])
    available_sol = float(state.get("available_sol", 1.0))
    initial_cap = float(state.get("initial_capital_sol", 1.0))

    # Build lookup map for live pairs
    pair_map = {p.get("raw_pair", p.get("pair")): p for p in live_pairs}
    for p in live_pairs:
        pair_map[p.get("pair")] = p
        base = p.get("base_token")
        if base:
            pair_map[f"SOL / {base}"] = p
            pair_map[f"{base}/SOL"] = p

    # -------------------------------------------------------------
    # 1. EVALUATE EXIT CONDITIONS FOR ACTIVE POSITIONS
    # -------------------------------------------------------------
    remaining_positions = []
    for pos in active_positions:
        pair_data = pair_map.get(pos.get("pair")) or pair_map.get(f"SOL / {pos.get('base_token')}")
        if not pair_data:
            remaining_positions.append(pos)
            continue

        curr_ratio = float(pair_data.get("current_ratio", pos.get("entry_ratio")))
        entry_ratio = float(pos.get("entry_ratio"))
        sol_invested = float(pos.get("sol_invested"))
        tokens_held = float(pos.get("tokens_held"))
        target_yield_pct = float(pos.get("target_yield_pct", 5.0))
        z_score = float(pair_data.get("z_score", 0.0))

        # Current gross SOL value of holding
        current_sol_val = tokens_held * curr_ratio
        gross_pnl_pct = ((curr_ratio - entry_ratio) / entry_ratio) * 100.0 if entry_ratio > 0 else 0.0

        # Exit Trigger: Mean-reversion achieved (Z >= -0.2σ) OR Target yield reached (+4.8%+)
        # Or holding time exceeded 48h with positive profit
        holding_hours = (now - pos.get("entry_time", now)) / 3600.0
        should_exit = False
        exit_reason = ""

        if z_score >= -0.20:
            should_exit = True
            exit_reason = f"Mean Reversion Achieved (Z={z_score:+.2f}σ)"
        elif gross_pnl_pct >= (target_yield_pct * 0.90):
            should_exit = True
            exit_reason = f"Target Profit Hit (+{gross_pnl_pct:.2f}%)"
        elif holding_hours >= 24.0 and gross_pnl_pct >= 2.5:
            should_exit = True
            exit_reason = f"Time Horizon Reached ({holding_hours:.1f}h, +{gross_pnl_pct:.2f}%)"
        elif time_offline >= 300 and holding_hours >= 0.5 and (gross_pnl_pct >= 2.0 or z_score >= -0.80):
            # Offline Catch-up: Position matured during offline period while PC was off
            should_exit = True
            exit_reason = f"Offline Mean Reversion (+{gross_pnl_pct:.2f}% while away)"

        if should_exit:
            # Deduct 0.20% DEX fee on exit
            net_sol_returned = current_sol_val * 0.9980
            profit_sol = net_sol_returned - sol_invested
            profit_pct = (profit_sol / sol_invested) * 100.0

            available_sol += net_sol_returned

            closed_trade = {
                "id": pos.get("id"),
                "pair": pos.get("pair"),
                "base_token": pos.get("base_token"),
                "entry_time": pos.get("entry_time"),
                "exit_time": now,
                "holding_duration_h": round(holding_hours, 1),
                "sol_invested": round(sol_invested, 4),
                "tokens_swapped": round(tokens_held, 4),
                "entry_ratio": entry_ratio,
                "exit_ratio": curr_ratio,
                "entry_z_score": pos.get("entry_z_score"),
                "exit_z_score": z_score,
                "sol_returned": round(net_sol_returned, 4),
                "net_profit_sol": round(profit_sol, 4),
                "net_profit_pct": round(profit_pct, 2),
                "exit_reason": exit_reason,
                "jupiter_route": f"SOL ➔ {pos.get('base_token')} ➔ SOL"
            }
            trade_history.insert(0, closed_trade) # Latest on top
        else:
            # Update live tracking info on open position
            pos["current_ratio"] = curr_ratio
            pos["current_sol_value"] = round(current_sol_val, 4)
            pos["unrealized_pnl_pct"] = round(gross_pnl_pct, 2)
            pos["current_z_score"] = round(z_score, 2)
            remaining_positions.append(pos)

    active_positions = remaining_positions

    # -------------------------------------------------------------
    # 2. EVALUATE ENTRY CONDITIONS FOR NEW POSITIONS
    # -------------------------------------------------------------
    max_positions = int(state.get("max_concurrent_positions", 2))
    
    # Check if we have an open slot and enough available capital
    if len(active_positions) < max_positions and available_sol >= 0.25:
        # Find candidates meeting oversold trigger (Z <= -2.0)
        candidates = []
        currently_held = {p.get("base_token") for p in active_positions}

        for p in live_pairs:
            base_token = p.get("base_token")
            z = float(p.get("z_score", 0.0))
            if base_token not in currently_held and z <= -2.0:
                candidates.append((z, p))

        # Sort by most oversold (lowest Z-score first, e.g. -2.72 before -2.10)
        candidates.sort(key=lambda x: x[0])

        slots_available = max_positions - len(active_positions)
        for _, pair_data in candidates[:slots_available]:
            base_token = pair_data.get("base_token")
            curr_ratio = float(pair_data.get("current_ratio", 0.0))
            if curr_ratio <= 0:
                continue

            # Allocation: tranche of available capital (max 0.45 SOL per slot)
            alloc_sol = min(0.45, available_sol * (1.0 / slots_available))
            if alloc_sol < 0.20:
                break

            # Deduct 0.15% DEX entry fee
            effective_sol = alloc_sol * 0.9985
            tokens_bought = effective_sol / curr_ratio

            new_pos = {
                "id": f"trade_{int(now)}_{base_token}",
                "pair": pair_data.get("pair"),
                "base_token": base_token,
                "quote_token": "SOL",
                "entry_time": now,
                "sol_invested": round(alloc_sol, 4),
                "tokens_held": round(tokens_bought, 4),
                "entry_ratio": curr_ratio,
                "current_ratio": curr_ratio,
                "entry_z_score": round(float(pair_data.get("z_score", 0.0)), 2),
                "current_z_score": round(float(pair_data.get("z_score", 0.0)), 2),
                "target_yield_pct": round(float(pair_data.get("target_yield_pct", 5.5)), 2),
                "unrealized_pnl_pct": 0.0,
                "current_sol_value": round(alloc_sol, 4),
                "status": "OPEN"
            }

            available_sol -= alloc_sol
            active_positions.append(new_pos)
            currently_held.add(base_token)

    # -------------------------------------------------------------
    # 3. RECALCULATE PORTFOLIO METRICS
    # -------------------------------------------------------------
    # Total portfolio equity = Available SOL + Current value of active positions
    positions_equity = sum(p.get("current_sol_value", p.get("sol_invested")) for p in active_positions)
    total_balance_sol = available_sol + positions_equity
    
    total_profit_sol = total_balance_sol - initial_cap
    total_profit_pct = (total_profit_sol / initial_cap) * 100.0

    state["available_sol"] = round(available_sol, 4)
    state["current_balance_sol"] = round(total_balance_sol, 4)
    state["total_profit_sol"] = round(total_profit_sol, 4)
    state["total_profit_pct"] = round(total_profit_pct, 2)
    state["active_positions"] = active_positions
    state["trade_history"] = trade_history[:50] # Keep latest 50 trades

    save_demo_state(state)
    return state
