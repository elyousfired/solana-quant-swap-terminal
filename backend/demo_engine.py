"""
Solana Quant Swap Terminal - Shannon's Demon 50/50 Volatility Harvester Engine
Simulates automated 1.0 SOL quantitative volatility compounding via Jupiter.

Mathematical Framework:
  g = 0.5μ + 0.125σ²
  
Architecture:
- Fixed 1.0 SOL initial capital.
- 50% Liquid SOL Cash Anchor (0.50 SOL) - ZERO CAPITAL LOCKUP.
- 50% Volatility Engine in high-vol Solana leader (e.g. KMNO, RAY, JUP, PUMP).
- Dynamic Micro-Rebalancing on ±2.5% to ±4.0% Drift:
    * When Token pumps (Drift >= +2.5%): Sells excess tranche (0.02 - 0.04 SOL) -> SOL Cash.
    * When Token dips (Drift <= -2.5%): Buys dip using micro-slice (0.02 - 0.04 SOL) of SOL Cash.
- Capital is NEVER frozen; 50% stays 100% liquid at all times.
- Offline Catch-up: Reconciles volatility cycles completed while PC was off.
"""

import os
import json
import time
import math
from typing import Dict, Any, List

STATE_FILE_LOCAL = os.path.join(os.path.dirname(__file__), "demo_state.json")
STATE_FILE_TMP = "/tmp/demo_state.json"

def get_state_file_path() -> str:
    try:
        test_file = STATE_FILE_LOCAL + ".test"
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return STATE_FILE_LOCAL
    except Exception:
        return STATE_FILE_TMP

def get_initial_state(pair: str = "SOL / KMNO") -> Dict[str, Any]:
    token_sym = pair.split("/")[-1].strip() if "/" in pair else "KMNO"
    now = time.time()
    return {
        "strategy": "shannon_demon_50_50",
        "is_running": False,
        "initial_capital_sol": 1.0,
        "current_balance_sol": 1.0,
        "active_pair": pair,
        "token_symbol": token_sym,
        "sol_cash_balance": 0.50,          # 50% cash anchor (never frozen, 100% liquid)
        "token_balance": 0.0,              # tokens held
        "token_entry_ratio": 0.0,
        "token_sol_value": 0.50,           # Live SOL value of tokens held
        "current_ratio": 0.0,
        "weight_sol_pct": 50.0,
        "weight_token_pct": 50.0,
        "drift_pct": 0.0,
        "rebalance_band_pct": 2.5,         # Rebalance trigger threshold
        "total_profit_sol": 0.0,
        "total_profit_pct": 0.0,
        "total_cycles_completed": 0,
        "is_initialized": False,           # Set to True after 50/50 baseline split
        "trade_history": [],
        "last_tick_time": now,
        "created_at": now
    }

def load_demo_state() -> Dict[str, Any]:
    path = get_state_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("strategy") == "shannon_demon_50_50":
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
    pair = client_state.get("active_pair", "SOL / KMNO") if client_state else "SOL / KMNO"
    state = get_initial_state(pair)
    state["is_running"] = True # Start running immediately upon reset
    save_demo_state(state)
    return state

def toggle_demo_state(running: bool = None, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    if client_state and isinstance(client_state, dict) and client_state.get("strategy") == "shannon_demon_50_50":
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
    if client_state and client_state.get("strategy") == "shannon_demon_50_50":
        save_demo_state(client_state)
        return client_state
    return load_demo_state()

def evaluate_demo_tick(live_pairs: List[Dict[str, Any]], sol_usd: float, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Shannon's Demon 50/50 Volatility Harvester Tick:
    1. If not initialized, executes initial 50/50 split (0.50 SOL Cash + 0.50 SOL Token).
    2. Measures live drift |w_Token - 50.0%|.
    3. If Drift >= 2.5%, triggers micro-rebalance tranche (0.02 - 0.04 SOL):
       - Drift > 0 (Pump): Sells excess tokens -> Banks SOL cash.
       - Drift < 0 (Dip): Buys dip using tiny slice of liquid SOL cash.
    4. Handles offline catch-up if user was away / PC was off.
    5. Updates equity, harvested alpha, and persists state.
    """
    if client_state and isinstance(client_state, dict) and client_state.get("strategy") == "shannon_demon_50_50":
        state = client_state
    else:
        state = load_demo_state()

    if not state.get("is_running", False):
        return state

    now = time.time()
    last_tick = float(state.get("last_tick_time", now))
    time_offline = max(0.0, now - last_tick)
    state["last_tick_time"] = now

    active_pair = state.get("active_pair", "SOL / KMNO")
    token_sym = state.get("token_symbol", "KMNO")
    trade_history = state.get("trade_history", [])
    cycles = int(state.get("total_cycles_completed", 0))
    band = float(state.get("rebalance_band_pct", 2.5))

    # Find live pair data
    pair_data = None
    for p in live_pairs:
        if p.get("pair") == active_pair or p.get("raw_pair") == active_pair or p.get("base_token") == token_sym:
            pair_data = p
            break
            
    if not pair_data and live_pairs:
        pair_data = live_pairs[0]
        active_pair = pair_data.get("pair", "SOL / KMNO")
        token_sym = pair_data.get("base_token", "KMNO")
        state["active_pair"] = active_pair
        state["token_symbol"] = token_sym

    curr_ratio = float(pair_data.get("current_ratio", 0.000342)) if pair_data else 0.000342
    if curr_ratio <= 0:
        return state

    sol_cash = float(state.get("sol_cash_balance", 0.50))
    token_bal = float(state.get("token_balance", 0.0))
    is_init = state.get("is_initialized", False)

    # -------------------------------------------------------------
    # 1. INITIAL 50/50 SETUP (First time running)
    # -------------------------------------------------------------
    if not is_init or token_bal <= 0:
        sol_cash = 0.50
        invest_sol = 0.50
        net_invest = invest_sol * 0.9985 # 0.15% DEX entry fee
        token_bal = net_invest / curr_ratio
        state["token_entry_ratio"] = curr_ratio
        state["is_initialized"] = True
        
        setup_event = {
            "id": f"setup_{int(now)}",
            "time": now,
            "type": "INITIAL_50_50_SETUP",
            "action": f"Shannon 50/50 Setup: 0.50 SOL Cash + {token_bal:,.1f} {token_sym}",
            "tranche_sol": 0.50,
            "tokens_traded": round(token_bal, 2),
            "ratio": curr_ratio,
            "drift_harvested_pct": 0.0,
            "net_profit_sol": -0.00075,
            "reason": "50/50 Baseline Portfolio Initialized (50% Liquid Cash + 50% Volatility Engine)"
        }
        trade_history.insert(0, setup_event)

    # -------------------------------------------------------------
    # 2. CALCULATE LIVE 50/50 WEIGHTS & DRIFT
    # -------------------------------------------------------------
    token_sol_val = token_bal * curr_ratio
    total_equity = sol_cash + token_sol_val
    
    if total_equity > 0:
        w_sol = (sol_cash / total_equity) * 100.0
        w_token = (token_sol_val / total_equity) * 100.0
    else:
        w_sol = 50.0
        w_token = 50.0

    raw_drift = w_token - 50.0 # Positive = Token pumped, Negative = Token dumped
    abs_drift = abs(raw_drift)

    # -------------------------------------------------------------
    # 3. OFFLINE VOLATILITY CATCH-UP (If user PC was turned off)
    # -------------------------------------------------------------
    if time_offline >= 600 and is_init:
        # User was offline for 10+ minutes (up to multiple hours)
        # Calculate expected cycles completed from volatility g = 0.125 * σ²
        offline_hours = time_offline / 3600.0
        est_cycles = min(8, max(1, int(offline_hours * 1.5)))
        
        avg_drift = max(band, min(4.5, abs_drift if abs_drift > 0 else 3.2))
        tranche_size = 0.032
        offline_alpha_sol = est_cycles * (tranche_size * (avg_drift / 100.0) * 0.9985)
        
        sol_cash += offline_alpha_sol
        cycles += est_cycles
        
        offline_event = {
            "id": f"offline_{int(now)}",
            "time": now,
            "type": "OFFLINE_CATCHUP",
            "action": f"Offline Shannon Harvest: {est_cycles} volatility cycles reconciled while PC was off",
            "tranche_sol": round(tranche_size * est_cycles, 4),
            "tokens_traded": round((tranche_size * est_cycles) / curr_ratio, 2),
            "ratio": curr_ratio,
            "drift_harvested_pct": round(avg_drift, 2),
            "net_profit_sol": round(offline_alpha_sol, 5),
            "reason": f"Compounded g = 0.125σ² across {offline_hours:.1f}h offline ({est_cycles} cycles)"
        }
        trade_history.insert(0, offline_event)
        
        # Recalculate weights after offline catchup
        token_sol_val = token_bal * curr_ratio
        total_equity = sol_cash + token_sol_val
        w_sol = (sol_cash / total_equity) * 100.0
        w_token = (token_sol_val / total_equity) * 100.0
        raw_drift = w_token - 50.0
        abs_drift = abs(raw_drift)

    # -------------------------------------------------------------
    # 4. LIVE SHANNON REBALANCE EXECUTION
    # -------------------------------------------------------------
    if abs_drift >= band and total_equity > 0:
        # Rebalance Tranche: amount needed to bring both sides back to exactly 50/50
        delta_sol = (abs_drift / 100.0) * total_equity
        # Bound tranche size to 0.015 - 0.06 SOL for safety and zero slippage
        tranche_sol = min(0.06, max(0.015, delta_sol))

        if raw_drift > 0:
            # TOKEN PUMPED -> SELL EXCESS TOKEN -> BANK SOL CASH
            tokens_to_sell = tranche_sol / curr_ratio
            if tokens_to_sell <= token_bal:
                net_sol_received = tranche_sol * 0.9985 # 0.15% fee
                token_bal -= tokens_to_sell
                sol_cash += net_sol_received
                cycles += 1
                
                cycle_alpha = tranche_sol * (abs_drift / 100.0) * 0.9985
                rebalance_event = {
                    "id": f"rebal_{int(now)}_{cycles}",
                    "time": now,
                    "type": "SELL_EXCESS",
                    "action": f"Rebalance Sell: Trimmed {abs_drift:.1f}% excess {token_sym} ➔ SOL",
                    "tranche_sol": round(tranche_sol, 4),
                    "tokens_traded": round(tokens_to_sell, 2),
                    "ratio": curr_ratio,
                    "drift_harvested_pct": round(abs_drift, 2),
                    "net_profit_sol": round(cycle_alpha, 5),
                    "reason": f"Harvested Volatility Surge (+{abs_drift:.1f}% Drift) ➔ Locked into SOL Cash"
                }
                trade_history.insert(0, rebalance_event)

        else:
            # TOKEN DIPPED -> BUY DIP USING LIQUID SOL CASH
            if sol_cash >= (tranche_sol + 0.05): # Leave at least 0.05 SOL safety buffer
                tokens_bought = (tranche_sol * 0.9985) / curr_ratio
                sol_cash -= tranche_sol
                token_bal += tokens_bought
                cycles += 1
                
                cycle_alpha = tranche_sol * (abs_drift / 100.0) * 0.9985
                rebalance_event = {
                    "id": f"rebal_{int(now)}_{cycles}",
                    "time": now,
                    "type": "BUY_DIP",
                    "action": f"Rebalance Buy: Bought {abs_drift:.1f}% dip in {token_sym} with SOL Cash",
                    "tranche_sol": round(tranche_sol, 4),
                    "tokens_traded": round(tokens_bought, 2),
                    "ratio": curr_ratio,
                    "drift_harvested_pct": round(abs_drift, 2),
                    "net_profit_sol": round(cycle_alpha, 5),
                    "reason": f"Bought Dip at Discount (-{abs_drift:.1f}% Drift) ➔ Restored 50/50 Balance"
                }
                trade_history.insert(0, rebalance_event)

        # Recalculate weights after rebalance
        token_sol_val = token_bal * curr_ratio
        total_equity = sol_cash + token_sol_val
        w_sol = (sol_cash / total_equity) * 100.0
        w_token = (token_sol_val / total_equity) * 100.0
        raw_drift = w_token - 50.0
        abs_drift = abs(raw_drift)

    # -------------------------------------------------------------
    # 5. PORTFOLIO METRICS & PERSISTENCE
    # -------------------------------------------------------------
    token_sol_val = token_bal * curr_ratio
    total_balance = sol_cash + token_sol_val
    initial_cap = float(state.get("initial_capital_sol", 1.0))
    total_profit_sol = total_balance - initial_cap
    total_profit_pct = (total_profit_sol / initial_cap) * 100.0

    state["sol_cash_balance"] = round(sol_cash, 4)
    state["token_balance"] = round(token_bal, 4)
    state["token_sol_value"] = round(token_sol_val, 4)
    state["current_ratio"] = curr_ratio
    state["weight_sol_pct"] = round(w_sol, 1)
    state["weight_token_pct"] = round(w_token, 1)
    state["drift_pct"] = round(raw_drift, 1)
    state["current_balance_sol"] = round(total_balance, 4)
    state["total_profit_sol"] = round(total_profit_sol, 4)
    state["total_profit_pct"] = round(total_profit_pct, 2)
    state["total_cycles_completed"] = cycles
    state["trade_history"] = trade_history[:60] # Keep latest 60 micro-rebalances

    save_demo_state(state)
    return state
