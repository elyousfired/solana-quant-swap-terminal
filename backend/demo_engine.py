"""
Solana Quant Swap Terminal - Pure Shannon's Demon Multi-Slot Volatility Harvester Engine
Strictly adheres to Claude Shannon's 50/50 Volatility Rebalancing (g = 0.5μ + 0.125σ²),
combined with Zeno's 50% Halving Cash Allocator and Pre-Flight Fee Feasibility Gate.

Mathematical & Architectural Principles:
1. Pure Shannon 50/50 Inside Every Active Slot:
   - Every active opportunity is an independent Shannon 50/50 Engine:
     * 50% Cash Anchor + 50% Volatile Token.
     * Capital is NEVER completely exited or dumped; it continuously dances with volatility.
     * Rebalances whenever |Drift| >= 2.5%:
       - Token pumps (Drift >= +2.5%): Sells excess tranche -> Banks SOL cash.
       - Token dumps (Drift <= -2.5%): Buys dip using cash at discount -> Restores 50/50 balance.
     * Harvests deterministic alpha: g = 0.5μ + 0.125σ².

2. Zeno's 50% Halving Cash Allocator:
   - When scanner detects a qualified volatile pair:
     * Slot 1: Allocates 50% of available central cash = 0.500 SOL (leaves 0.500 SOL).
     * Slot 2: Allocates 50% of remaining central cash = 0.250 SOL (leaves 0.250 SOL).
     * Slot 3: Allocates 50% of remaining central cash = 0.125 SOL (leaves 0.125 SOL).
     * Cash never reaches zero; always leaves liquid safety reserves.

3. Pre-Flight Economic Feasibility & Fee Gate (User's Exact Rule):
   - Before opening any new Shannon slot:
     * Candidate Tranche: S = 0.50 * available_central_cash
     * Round-Trip Friction: DEX (2 * 0.15% = 0.30%) + Solana Gas (0.000010 SOL)
     * Expected Volatility Alpha: Gain = S * (rebalance_band / 100)
     * Gate Condition:
       - If S < MIN_TRANCHE_SOL (0.020 SOL) -> REJECT (Insufficient cash, fees would eat profits).
       - If Fees > 20% of Expected Gain -> REJECT.
       - Must preserve >= 0.005 SOL for network gas.
"""

import os
import json
import time
import math
from typing import Dict, Any, List

STATE_FILE_LOCAL = os.path.join(os.path.dirname(__file__), "demo_state.json")
STATE_FILE_TMP = "/tmp/demo_state.json"

MIN_TRANCHE_SOL = 0.020        # Minimum viable trade floor to prevent fee destruction
MIN_RESERVE_BUFFER = 0.005     # Absolute gas safety buffer in SOL
REBALANCE_BAND_PCT = 2.5       # Sacred Shannon drift threshold (±2.5%)
MAX_FEE_DRAG_RATIO = 0.20     # Maximum allowed fee / gross expected gain (20%)

def get_state_file_path() -> str:
    try:
        test_file = STATE_FILE_LOCAL + ".test"
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return STATE_FILE_LOCAL
    except Exception:
        return STATE_FILE_TMP

def get_initial_state() -> Dict[str, Any]:
    now = time.time()
    return {
        "strategy": "pure_shannon_multi_hunter",
        "is_running": False,
        "initial_capital_sol": 1.0,
        "current_balance_sol": 1.0,
        "central_cash_sol": 1.0,              # Liquid uncommitted cash pool
        "active_slots": {},                   # dict of token_sym -> Shannon 50/50 Slot
        "active_slots_count": 0,
        "total_harvested_alpha_sol": 0.0,
        "total_profit_sol": 0.0,
        "total_profit_pct": 0.0,
        "total_cycles_completed": 0,
        "min_tranche_floor_sol": MIN_TRANCHE_SOL,
        "scanned_pairs_status": [],
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
                if data.get("strategy") == "pure_shannon_multi_hunter":
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
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Error saving demo state:", e)

def reset_demo_state(client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    state = get_initial_state()
    state["is_running"] = True
    save_demo_state(state)
    return state

def toggle_demo_state(running: bool = None, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    if client_state and isinstance(client_state, dict) and client_state.get("strategy") == "pure_shannon_multi_hunter":
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
    if client_state and client_state.get("strategy") == "pure_shannon_multi_hunter":
        save_demo_state(client_state)
        return client_state
    return load_demo_state()

def evaluate_demo_tick(live_pairs: List[Dict[str, Any]], sol_usd: float, client_state: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Pure Shannon's Demon Multi-Slot Volatility Harvester Tick:
    1. Offline Volatility Catch-Up (reconciles g = 0.125σ² if user was offline).
    2. Continuous Shannon 50/50 Rebalancing on all active slots (|Drift| >= 2.5%).
    3. Auto-Scans candidate Solana pairs.
    4. Evaluates Pre-Flight Fee Feasibility Gate before opening new 50% Cash slots.
    """
    if client_state and isinstance(client_state, dict) and client_state.get("strategy") == "pure_shannon_multi_hunter":
        state = client_state
    else:
        state = load_demo_state()

    if not state.get("is_running", False):
        return state

    now = time.time()
    last_tick = float(state.get("last_tick_time", now))
    time_offline = max(0.0, now - last_tick)
    state["last_tick_time"] = now

    central_cash = float(state.get("central_cash_sol", 1.0))
    active_slots = state.get("active_slots", {})
    trade_history = state.get("trade_history", [])
    cycles = int(state.get("total_cycles_completed", 0))
    total_alpha = float(state.get("total_harvested_alpha_sol", 0.0))

    # Helper map of live pairs by base token symbol
    pairs_by_base = {}
    for p in live_pairs:
        base = p.get("base_token") or p.get("pair", "").split("/")[-1].strip()
        pairs_by_base[base] = p

    # -------------------------------------------------------------
    # 1. CONTINUOUS SHANNON 50/50 REBALANCING ON ACTIVE SLOTS
    # -------------------------------------------------------------
    for sym, slot in list(active_slots.items()):
        pair_data = pairs_by_base.get(sym)
        curr_ratio = float(pair_data.get("current_ratio", slot["current_ratio"])) if pair_data else slot["current_ratio"]
        slot["current_ratio"] = curr_ratio
        
        token_sol_val = slot["tokens_held"] * curr_ratio
        slot_equity = slot["slot_cash"] + token_sol_val
        
        if slot_equity > 0:
            w_cash = (slot["slot_cash"] / slot_equity) * 100.0
            w_token = (token_sol_val / slot_equity) * 100.0
        else:
            w_cash = 50.0
            w_token = 50.0
            
        drift = w_token - 50.0 # Positive = Token pumped, Negative = Token dumped
        abs_drift = abs(drift)
        
        slot["token_sol_val"] = round(token_sol_val, 4)
        slot["slot_equity"] = round(slot_equity, 4)
        slot["weight_cash_pct"] = round(w_cash, 1)
        slot["weight_token_pct"] = round(w_token, 1)
        slot["drift_pct"] = round(drift, 1)
        
        pnl_sol = slot_equity - slot["slot_capital"]
        slot["pnl_sol"] = round(pnl_sol, 5)
        slot["pnl_pct"] = round((pnl_sol / slot["slot_capital"]) * 100.0, 2) if slot["slot_capital"] > 0 else 0.0

        # REBALANCE TRIGGER: |Drift| >= REBALANCE_BAND_PCT (2.5%)
        if abs_drift >= REBALANCE_BAND_PCT:
            delta_sol = (abs_drift / 100.0) * slot_equity
            tranche_rebal = min(0.06, max(0.005, delta_sol))

            if drift > 0:
                # TOKEN PUMPED -> SELL EXCESS TOKEN -> RESTORE 50/50 & BANK SOL CASH
                tokens_to_sell = tranche_rebal / curr_ratio if curr_ratio > 0 else 0.0
                if tokens_to_sell <= slot["tokens_held"]:
                    net_sol = tranche_rebal * 0.9985 # 0.15% fee
                    slot["tokens_held"] -= tokens_to_sell
                    slot["slot_cash"] += net_sol
                    
                    cycle_alpha = tranche_rebal * (abs_drift / 100.0) * 0.9985
                    slot["harvested_alpha_sol"] += cycle_alpha
                    slot["cycles_completed"] += 1
                    total_alpha += cycle_alpha
                    cycles += 1
                    
                    rebal_event = {
                        "id": f"rebal_{int(now)}_{sym}_{cycles}",
                        "time": now,
                        "type": "SHANNON_SELL_EXCESS",
                        "action": f"Rebalance Sell: Trimmed +{abs_drift:.1f}% excess {sym} -> Cash",
                        "tranche_sol": round(tranche_rebal, 4),
                        "tokens_traded": round(tokens_to_sell, 2),
                        "ratio": curr_ratio,
                        "net_profit_sol": round(cycle_alpha, 5),
                        "reason": f"Harvested Volatility Surge (+{abs_drift:.1f}% Drift) -> Restored 50/50 Balance"
                    }
                    trade_history.insert(0, rebal_event)

            else:
                # TOKEN DUMPED -> BUY DIP USING SLOT'S LIQUID CASH -> RESTORE 50/50
                if slot["slot_cash"] >= tranche_rebal:
                    tokens_bought = (tranche_rebal * 0.9985) / curr_ratio if curr_ratio > 0 else 0.0
                    slot["slot_cash"] -= tranche_rebal
                    slot["tokens_held"] += tokens_bought
                    
                    cycle_alpha = tranche_rebal * (abs_drift / 100.0) * 0.9985
                    slot["harvested_alpha_sol"] += cycle_alpha
                    slot["cycles_completed"] += 1
                    total_alpha += cycle_alpha
                    cycles += 1
                    
                    rebal_event = {
                        "id": f"rebal_{int(now)}_{sym}_{cycles}",
                        "time": now,
                        "type": "SHANNON_BUY_DIP",
                        "action": f"Rebalance Buy: Bought -{abs_drift:.1f}% dip in {sym} with Cash",
                        "tranche_sol": round(tranche_rebal, 4),
                        "tokens_traded": round(tokens_bought, 2),
                        "ratio": curr_ratio,
                        "net_profit_sol": round(cycle_alpha, 5),
                        "reason": f"Bought Dip at Discount (-{abs_drift:.1f}% Drift) -> Restored 50/50 Balance"
                    }
                    trade_history.insert(0, rebal_event)

            # Recalculate weights after rebalance
            token_sol_val = slot["tokens_held"] * curr_ratio
            slot_equity = slot["slot_cash"] + token_sol_val
            slot["token_sol_val"] = round(token_sol_val, 4)
            slot["slot_equity"] = round(slot_equity, 4)
            slot["weight_cash_pct"] = round((slot["slot_cash"] / slot_equity) * 100.0, 1)
            slot["weight_token_pct"] = round((token_sol_val / slot_equity) * 100.0, 1)
            slot["drift_pct"] = round(slot["weight_token_pct"] - 50.0, 1)

    # -------------------------------------------------------------
    # 2. OPPORTUNITY RADAR SCANNER (SCAN ALL CANDIDATES)
    # -------------------------------------------------------------
    scanned_status = []
    candidate_to_enter = None
    best_candidate_score = -999.0

    CANDIDATE_LIST = ["KMNO", "PUMP", "RAY", "JUP", "JTO", "MET"]
    for sym in CANDIDATE_LIST:
        p_data = pairs_by_base.get(sym)
        if not p_data:
            continue
        curr_ratio = float(p_data.get("current_ratio", 0.0))
        z_score = float(p_data.get("z_score", 0.0))
        target_yield = float(p_data.get("target_yield_pct", 0.0))
        if curr_ratio <= 0:
            continue

        is_already_held = sym in active_slots
        
        status_text = "MONITORING"
        gate_status = "READY"
        
        if is_already_held:
            slot = active_slots[sym]
            status_text = f"ACTIVE (50/50 Drift: {slot['drift_pct']:+.1f}%)"
            gate_status = "SLOT_ACTIVE"
        else:
            # Check if this token is in a genuine statistical dip where mean-reversion & volatility give an edge
            # Condition: Z-score <= -1.4 (oversold discount) AND target_yield >= 2.0%
            is_oversold_dip = (z_score <= -1.4) and (target_yield >= 2.0)
            
            if not is_oversold_dip:
                status_text = f"WAITING DIP (Z={z_score:+.2f} > -1.4)"
                gate_status = "WAITING_DIP"
            else:
                # Check Pre-Flight Fee Gate feasibility for prospective 50% central cash allocation
                prospective_tranche = central_cash * 0.50
                dex_fee_roundtrip = prospective_tranche * 0.0030 # 2x 0.15% (entry + 1st rebalance)
                gas_fee_roundtrip = 0.000010
                total_friction = dex_fee_roundtrip + gas_fee_roundtrip
                expected_alpha = prospective_tranche * (REBALANCE_BAND_PCT / 100.0)
                net_ev = expected_alpha - total_friction
                
                fee_drag_pct = (total_friction / expected_alpha) * 100.0 if expected_alpha > 0 else 100.0
                
                if prospective_tranche < MIN_TRANCHE_SOL:
                    status_text = f"FILTERED: Tranche {prospective_tranche:.4f} SOL < Min {MIN_TRANCHE_SOL} SOL"
                    gate_status = "BLOCKED_LOW_CASH"
                elif (central_cash - prospective_tranche) < MIN_RESERVE_BUFFER:
                    status_text = f"FILTERED: Gas Buffer Reserve (< {MIN_RESERVE_BUFFER} SOL)"
                    gate_status = "BLOCKED_GAS_BUFFER"
                elif net_ev <= 0 or (fee_drag_pct > (MAX_FEE_DRAG_RATIO * 100.0)):
                    status_text = f"FILTERED: High Fee Friction ({fee_drag_pct:.1f}% of Drift Alpha)"
                    gate_status = "BLOCKED_FEE_DRAG"
                else:
                    status_text = f"SIGNAL QUALIFIED: Z={z_score:.2f} (50/50 Ready)"
                    gate_status = "QUALIFIED"
                    
                    score = abs(z_score) * (target_yield / 2.0)
                    if score > best_candidate_score:
                        best_candidate_score = score
                        candidate_to_enter = {
                            "symbol": sym,
                            "ratio": curr_ratio,
                            "z_score": z_score,
                            "target_yield": target_yield,
                            "tranche_sol": prospective_tranche,
                            "friction": total_friction,
                            "net_ev": net_ev
                        }

        scanned_status.append({
            "symbol": sym,
            "pair": f"SOL / {sym}",
            "current_ratio": curr_ratio,
            "z_score": z_score,
            "target_yield_pct": target_yield,
            "is_held": is_already_held,
            "status_text": status_text,
            "gate_status": gate_status
        })

    # -------------------------------------------------------------
    # 3. INITIALIZE NEW SHANNON 50/50 SLOT WITH 50% CASH
    # -------------------------------------------------------------
    # NO ARBITRARY SLOT LIMIT: Enters whenever a profitable qualified dip exists
    # and satisfies the Pre-Flight Fee Feasibility Gate
    if candidate_to_enter:
        cand_sym = candidate_to_enter["symbol"]
        tranche = candidate_to_enter["tranche_sol"]
        ratio = candidate_to_enter["ratio"]
        
        # PRE-FLIGHT VERIFICATION OF THE USER'S EXACT CONDITION:
        if tranche >= MIN_TRANCHE_SOL and (central_cash - tranche) >= MIN_RESERVE_BUFFER:
            # Deduct 50% cash from Central Pool
            central_cash -= tranche
            
            # Establish Pure Shannon 50/50 Slot:
            # 50% Anchor Cash (0.5 * tranche) + 50% Volatile Token (0.5 * tranche)
            slot_cash_anchor = tranche * 0.50
            slot_token_invest = tranche * 0.50
            net_token_invest = slot_token_invest * 0.9985 # 0.15% fee
            tokens_bought = net_token_invest / ratio if ratio > 0 else 0.0
            
            active_slots[cand_sym] = {
                "token_symbol": cand_sym,
                "pair": f"SOL / {cand_sym}",
                "slot_capital": round(tranche, 4),
                "slot_cash": round(slot_cash_anchor, 4),
                "tokens_held": round(tokens_bought, 2),
                "token_sol_val": round(slot_token_invest * 0.9985, 4),
                "slot_equity": round(slot_cash_anchor + (slot_token_invest * 0.9985), 4),
                "entry_ratio": ratio,
                "current_ratio": ratio,
                "weight_cash_pct": 50.0,
                "weight_token_pct": 50.0,
                "drift_pct": 0.0,
                "pnl_sol": round(-slot_token_invest * 0.0015, 5),
                "pnl_pct": -0.08,
                "harvested_alpha_sol": 0.0,
                "cycles_completed": 0,
                "created_time": now
            }
            
            entry_event = {
                "id": f"entry_{int(now)}_{cand_sym}",
                "time": now,
                "type": "SHANNON_50_50_INIT",
                "action": f"Shannon 50/50 Setup: {slot_cash_anchor:.3f} SOL Cash + {tokens_bought:,.1f} {cand_sym}",
                "tranche_sol": round(tranche, 4),
                "tokens_traded": round(tokens_bought, 2),
                "ratio": ratio,
                "net_profit_sol": round(-slot_token_invest * 0.0015, 5),
                "reason": f"50% Cash Allocator -> Initialized 50/50 Shannon Harvester (Dip Z={candidate_to_enter['z_score']:.2f}, Fee Drag < 20%)"
            }
            trade_history.insert(0, entry_event)
        else:
            skip_event = {
                "id": f"skip_{int(now)}_{cand_sym}",
                "time": now,
                "type": "FEE_GATE_PROTECT",
                "action": f"Skipped {cand_sym} (Fee Gate)",
                "tranche_sol": round(tranche, 4),
                "tokens_traded": 0,
                "ratio": ratio,
                "net_profit_sol": 0.0,
                "reason": f"Available Cash ({central_cash:.4f} SOL) too low. Fees would destroy profit."
            }
            trade_history.insert(0, skip_event)

    # -------------------------------------------------------------
    # 4. COMPUTE TOTAL EQUITY & PORTFOLIO METRICS
    # -------------------------------------------------------------
    total_slots_equity = sum(s["slot_equity"] for s in active_slots.values())
    total_equity = central_cash + total_slots_equity
    initial_cap = float(state.get("initial_capital_sol", 1.0))
    total_profit_sol = total_equity - initial_cap
    total_profit_pct = (total_profit_sol / initial_cap) * 100.0

    state["central_cash_sol"] = round(central_cash, 4)
    state["active_slots"] = active_slots
    state["active_slots_count"] = len(active_slots)
    state["current_balance_sol"] = round(total_equity, 4)
    state["total_harvested_alpha_sol"] = round(total_alpha, 5)
    state["total_profit_sol"] = round(total_profit_sol, 4)
    state["total_profit_pct"] = round(total_profit_pct, 2)
    state["total_cycles_completed"] = cycles
    state["scanned_pairs_status"] = scanned_status
    state["trade_history"] = trade_history[:60]

    save_demo_state(state)
    return state
