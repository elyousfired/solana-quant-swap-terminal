"""
Solana Quant Swap Terminal - Pure Claude Shannon 6-Basket 50/50 Threshold Rebalancing Engine
Written from scratch to implement authentic Claude Shannon's Demon (MIT, 1960s) with
Threshold Drift Band Rebalancing across all 6 Solana ecosystem pairs simultaneously.

Core Strategy Architecture:
1. Equal 6-Basket Simultaneous Deployment (1.0000 SOL Initial Capital):
   - Dedicated Solana Network Gas Reserve: 0.0400 SOL (4.0% untouched gas buffer).
   - Deployable Capital: 0.9600 SOL split equally across 6 volatile Solana pairs:
     [JUP, RAY, JTO, KMNO, MET, PUMP] -> Exact 0.1600 SOL per Basket.
   - Inside Every Basket (50% / 50% Value Scale at Entry):
     * Kaffa 1 (SOL Cash Anchor): 0.0800 SOL liquid cash held inside the basket.
     * Kaffa 2 (Volatile Token):  0.0800 SOL swapped into the basket's token at live Jupiter price
       (net of realistic 0.15% DEX swap fee + 0.000005 SOL network tx fee).
   - Zero directional guessing, zero Z-score dip waiting: captures both pumps and dumps from t=0.

2. Pure Price-Driven Value Scale (الميزان = Quantity × Live Price):
   - At every live tick, for basket i with live exchange rate P_t (SOL per 1 Token):
     * Cash Value:   C_t = slot_cash (SOL)
     * Token Value:  V_t = tokens_held * P_t (SOL)
     * Basket Equity: E_t = C_t + V_t (SOL)
     * Token Weight: w_token = (V_t / E_t) * 100%
     * Cash Weight:  w_cash  = (C_t / E_t) * 100%
     * Drift:        Drift   = w_token - 50.0%

3. Threshold Drift Band Rebalancing (|Drift| >= 2.5%, i.e. 52.5% / 47.5%):
   - No time/calendar rebalancing (prevents fee bleed in flat markets).
   - Triggers strictly when |w_token - 50.0%| >= REBALANCE_BAND_PCT (2.5%):
     * Exact Rebalance Trade Size: delta_sol = |V_t - C_t| / 2.0
     * Pre-Flight Fee Gate verifies expected volatility harvest exceeds total swap + gas friction.
     * If Drift >= +2.5% (Token Pumped vs SOL):
       Sells exact excess tokens (delta_sol / P_t) -> adds net SOL into basket's slot_cash.
       Restores 50.0% / 50.0% balance at the NEW higher price!
     * If Drift <= -2.5% (Token Dropped vs SOL):
       Spends exact excess SOL (delta_sol) from basket's slot_cash -> buys discounted tokens.
       Restores 50.0% / 50.0% balance at the NEW lower price!
   - Zero fake offline estimations: 100% real mark-to-market ledger accounting.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional

STRATEGY_ID = "shannon_6basket_threshold_v1"

BASKET_TOKENS = ["JUP", "RAY", "JTO", "KMNO", "MET", "PUMP"]
INITIAL_CAPITAL_SOL = 1.0000
INITIAL_GAS_RESERVE_SOL = 0.0400
DEPLOYABLE_CAPITAL_SOL = INITIAL_CAPITAL_SOL - INITIAL_GAS_RESERVE_SOL  # 0.9600 SOL
BASKET_ALLOCATION_SOL = DEPLOYABLE_CAPITAL_SOL / len(BASKET_TOKENS)     # 0.1600 SOL per basket

REBALANCE_BAND_PCT = 1.0         # Threshold Drift Band: |w_token - 50%| >= 1.0% (~4.0% price move)
DEX_FEE_RATE = 0.0015            # 0.15% realistic Jupiter DEX swap fee
SOL_TX_GAS_FEE = 0.000005        # 0.000005 SOL Solana network transaction fee
MIN_REBALANCE_SOL = 0.0008       # Minimum swap size floor in SOL
MIN_GAS_FLOOR_SOL = 0.0010       # Minimum gas reserve floor in SOL

STATE_FILE_LOCAL = os.path.join(os.path.dirname(__file__), "demo_state.json")
STATE_FILE_TMP = "/tmp/demo_state.json"


def get_state_file_path() -> str:
    try:
        test_file = STATE_FILE_LOCAL + ".test"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return STATE_FILE_LOCAL
    except Exception:
        return STATE_FILE_TMP


def get_initial_state() -> Dict[str, Any]:
    now = time.time()
    return {
        "strategy": STRATEGY_ID,
        "is_running": True,
        "initial_capital_sol": INITIAL_CAPITAL_SOL,
        "sol_price_usd": 95.50,
        "rebalance_band_pct": REBALANCE_BAND_PCT,
        "basket_allocation_sol": BASKET_ALLOCATION_SOL,
        "gas_reserve_sol": INITIAL_GAS_RESERVE_SOL,
        "initial_gas_after_init_sol": INITIAL_GAS_RESERVE_SOL,
        "unallocated_cash_sol": DEPLOYABLE_CAPITAL_SOL,
        "central_cash_sol": INITIAL_GAS_RESERVE_SOL + DEPLOYABLE_CAPITAL_SOL,
        "total_basket_cash_sol": 0.0,
        "total_liquid_sol": INITIAL_CAPITAL_SOL,
        "total_token_val_sol": 0.0,
        "current_balance_sol": INITIAL_CAPITAL_SOL,
        "hodl_benchmark_sol": INITIAL_CAPITAL_SOL,
        "rebalance_surplus_sol": 0.0,
        "total_harvested_alpha_sol": 0.0,
        "total_fees_paid_sol": 0.0,
        "total_profit_sol": 0.0,
        "total_profit_pct": 0.0,
        "active_slots": {},
        "active_slots_count": 0,
        "total_cycles_completed": 0,
        "scanned_pairs_status": [],
        "trade_history": [],
        "last_tick_time": now,
        "created_at": now,
    }


def _is_valid_strategy_state(data: Optional[Dict[str, Any]]) -> bool:
    return bool(data and isinstance(data, dict) and data.get("strategy") == STRATEGY_ID)


def load_demo_state() -> Dict[str, Any]:
    path = get_state_file_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if _is_valid_strategy_state(data):
                    return data
        except Exception:
            pass
    state = get_initial_state()
    save_demo_state(state)
    return state


def save_demo_state(state: Dict[str, Any]) -> None:
    path = get_state_file_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Error saving demo state:", e)


def reset_demo_state(client_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = get_initial_state()
    state["is_running"] = True
    save_demo_state(state)
    return state


def toggle_demo_state(
    running: Optional[bool] = None,
    client_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if _is_valid_strategy_state(client_state):
        state = client_state
    else:
        state = load_demo_state()

    if running is None:
        state["is_running"] = not state.get("is_running", False)
    else:
        state["is_running"] = bool(running)

    state["last_tick_time"] = time.time()
    save_demo_state(state)
    return state


def sync_demo_state(client_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if _is_valid_strategy_state(client_state):
        save_demo_state(client_state)
        return client_state
    return load_demo_state()


def evaluate_demo_tick(
    live_pairs: List[Dict[str, Any]],
    sol_usd: float,
    client_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes one live tick of the Pure Claude Shannon 6-Basket 50/50 Threshold Drift Band Strategy:
    1. Deploys any uninitialized basket among [JUP, RAY, JTO, KMNO, MET, PUMP] at exact 50/50
       (0.0800 SOL Cash + 0.0800 SOL Token).
    2. Marks all 6 baskets to live Jupiter exchange rates (Value = Quantity * Live Price).
    3. Triggers exact 50/50 Threshold Rebalancing whenever |w_token - 50.0%| >= 1.0% (~4% price move)
       and Pre-Flight Fee Gate confirms positive net volatility harvest.
    4. Updates full portfolio equity, static 50/50 HODL benchmark comparison, and audit ledger.
    """
    if _is_valid_strategy_state(client_state):
        state = client_state
    else:
        state = load_demo_state()

    if sol_usd and sol_usd > 0:
        state["sol_price_usd"] = round(float(sol_usd), 2)

    if not state.get("is_running", False):
        return state

    now = time.time()
    state["last_tick_time"] = now

    # Always enforce latest calibrated threshold band (1.0% weight drift = ~4.0% price move)
    band_pct = REBALANCE_BAND_PCT
    state["rebalance_band_pct"] = band_pct
    gas_reserve = float(state.get("gas_reserve_sol", INITIAL_GAS_RESERVE_SOL))
    initial_gas_after_init = float(state.get("initial_gas_after_init_sol", INITIAL_GAS_RESERVE_SOL))
    unallocated_cash = float(state.get("unallocated_cash_sol", 0.0))
    active_slots: Dict[str, Dict[str, Any]] = state.get("active_slots", {})
    trade_history: List[Dict[str, Any]] = state.get("trade_history", [])
    cycles = int(state.get("total_cycles_completed", 0))
    total_alpha = float(state.get("total_harvested_alpha_sol", 0.0))
    total_fees_paid = float(state.get("total_fees_paid_sol", 0.0))

    # Map live Jupiter pairs by token symbol (JUP, RAY, JTO, KMNO, MET, PUMP)
    pairs_by_base: Dict[str, Dict[str, Any]] = {}
    for p in live_pairs:
        base = p.get("base_token") or p.get("pair", "").split("/")[-1].strip()
        if base:
            pairs_by_base[base] = p

    # -------------------------------------------------------------------------
    # STEP 1: INITIALIZE ALL 6 BASKETS AT EXACT 50/50 (0.0800 SOL + 0.0800 TOKEN)
    # -------------------------------------------------------------------------
    for sym in BASKET_TOKENS:
        if sym in active_slots:
            continue

        p_data = pairs_by_base.get(sym)
        if not p_data:
            continue

        curr_ratio = float(p_data.get("current_ratio", 0.0))
        if curr_ratio <= 0:
            continue

        if unallocated_cash + 1e-9 < BASKET_ALLOCATION_SOL or gas_reserve <= MIN_GAS_FLOOR_SOL:
            continue

        basket_cap = min(BASKET_ALLOCATION_SOL, unallocated_cash)
        unallocated_cash = max(0.0, unallocated_cash - basket_cap)

        # 50% stays as liquid SOL Cash Anchor, 50% swaps into Token at live price
        cash_half = basket_cap * 0.50
        token_half_gross = basket_cap * 0.50
        dex_fee = token_half_gross * DEX_FEE_RATE
        net_token_sol = token_half_gross - dex_fee
        tokens_bought = net_token_sol / curr_ratio

        gas_reserve -= SOL_TX_GAS_FEE
        initial_gas_after_init -= SOL_TX_GAS_FEE
        entry_fee_total = dex_fee + SOL_TX_GAS_FEE
        total_fees_paid += entry_fee_total

        slot_eq = cash_half + net_token_sol
        w_cash = (cash_half / slot_eq) * 100.0
        w_tok = (net_token_sol / slot_eq) * 100.0

        active_slots[sym] = {
            "token_symbol": sym,
            "pair": f"SOL / {sym}",
            "slot_capital": basket_cap,
            "initial_cash": cash_half,
            "initial_tokens": tokens_bought,
            "slot_cash": cash_half,
            "tokens_held": tokens_bought,
            "token_sol_val": round(net_token_sol, 6),
            "slot_equity": round(slot_eq, 6),
            "entry_ratio": curr_ratio,
            "last_rebal_ratio": curr_ratio,
            "current_ratio": curr_ratio,
            "price_change_from_ref_pct": 0.0,
            "weight_cash_pct": round(w_cash, 2),
            "weight_token_pct": round(w_tok, 2),
            "drift_pct": round(w_tok - 50.0, 2),
            "pnl_sol": round(slot_eq - basket_cap, 6),
            "pnl_pct": round(((slot_eq - basket_cap) / basket_cap) * 100.0, 2),
            "harvested_alpha_sol": 0.0,
            "fees_paid_sol": round(entry_fee_total, 6),
            "cycles_completed": 0,
            "last_action": "50/50 INITIALIZED",
            "created_time": now,
        }

        trade_history.insert(
            0,
            {
                "id": f"init_{int(now * 1000)}_{sym}",
                "time": now,
                "type": "SHANNON_50_50_INIT",
                "symbol": sym,
                "action": f"Basket {sym} 50/50: {cash_half:.4f} SOL Cash + {tokens_bought:,.2f} {sym}",
                "tranche_sol": round(token_half_gross, 4),
                "tokens_traded": round(tokens_bought, 4),
                "ratio": curr_ratio,
                "net_profit_sol": round(-entry_fee_total, 6),
                "reason": f"Equal 1/6 Basket Setup ({basket_cap:.4f} SOL -> 50% SOL / 50% {sym})",
            },
        )

    # -------------------------------------------------------------------------
    # STEP 2: MARK-TO-MARKET & THRESHOLD DRIFT BAND REBALANCING (|Drift| >= 2.5%)
    # -------------------------------------------------------------------------
    scanned_status: List[Dict[str, Any]] = []

    for sym in BASKET_TOKENS:
        p_data = pairs_by_base.get(sym)
        slot = active_slots.get(sym)

        if not slot:
            live_r = float(p_data.get("current_ratio", 0.0)) if p_data else 0.0
            scanned_status.append(
                {
                    "symbol": sym,
                    "pair": f"SOL / {sym}",
                    "entry_ratio": live_r,
                    "last_rebal_ratio": live_r,
                    "current_ratio": live_r,
                    "price_change_ref_pct": 0.0,
                    "weight_cash_pct": 50.0,
                    "weight_token_pct": 50.0,
                    "drift_pct": 0.0,
                    "band_pct": band_pct,
                    "progress_to_trigger_pct": 0.0,
                    "slot_equity": 0.0,
                    "cycles_completed": 0,
                    "is_held": False,
                    "gate_status": "AWAITING_FEED",
                    "status_text": "Waiting for live Jupiter price feed",
                }
            )
            continue

        # Update basket with latest live Jupiter price (SOL per 1 Token)
        if p_data and float(p_data.get("current_ratio", 0.0)) > 0:
            curr_ratio = float(p_data["current_ratio"])
            slot["current_ratio"] = curr_ratio
        else:
            curr_ratio = float(slot["current_ratio"])

        cash_val = float(slot["slot_cash"])
        tokens_held = float(slot["tokens_held"])
        token_val = tokens_held * curr_ratio
        slot_equity = cash_val + token_val

        w_cash = (cash_val / slot_equity) * 100.0 if slot_equity > 0 else 50.0
        w_token = (token_val / slot_equity) * 100.0 if slot_equity > 0 else 50.0
        drift = w_token - 50.0
        abs_drift = abs(drift)

        ref_ratio = float(slot.get("last_rebal_ratio") or slot.get("entry_ratio") or curr_ratio)
        price_chg_ref_pct = ((curr_ratio - ref_ratio) / ref_ratio) * 100.0 if ref_ratio > 0 else 0.0

        rebalanced_this_tick = False
        fee_blocked_this_tick = False

        # Check Threshold Drift Band Trigger: |w_token - 50.0%| >= band_pct
        if abs_drift >= band_pct and slot_equity > 0 and curr_ratio > 0:
            # Exact SOL amount to move from heavy side to light side to restore 50.0% / 50.0%
            delta_sol = abs(token_val - cash_val) / 2.0
            dex_fee = delta_sol * DEX_FEE_RATE
            total_fee = dex_fee + SOL_TX_GAS_FEE

            # Quadratic volatility harvest generated by this rebalance step
            rel_move = max(abs(price_chg_ref_pct) / 100.0, (4.0 * abs_drift) / 100.0)
            gross_step_alpha = 0.5 * delta_sol * rel_move

            if (
                delta_sol >= MIN_REBALANCE_SOL
                and gas_reserve >= MIN_GAS_FLOOR_SOL
                and total_fee < gross_step_alpha
            ):
                if drift > 0:
                    # TOKEN PUMPED -> Token Kaffa > 50% -> Sell exact excess tokens into SOL Cash
                    tokens_to_sell = min(tokens_held, delta_sol / curr_ratio)
                    gross_sol_out = tokens_to_sell * curr_ratio
                    actual_dex_fee = gross_sol_out * DEX_FEE_RATE
                    net_sol_out = gross_sol_out - actual_dex_fee
                    actual_total_fee = actual_dex_fee + SOL_TX_GAS_FEE

                    tokens_held -= tokens_to_sell
                    cash_val += net_sol_out
                    gas_reserve -= SOL_TX_GAS_FEE

                    net_step_alpha = max(0.0, gross_step_alpha - actual_total_fee)
                    slot["slot_cash"] = cash_val
                    slot["tokens_held"] = tokens_held
                    slot["last_rebal_ratio"] = curr_ratio
                    slot["harvested_alpha_sol"] = float(slot.get("harvested_alpha_sol", 0.0)) + net_step_alpha
                    slot["fees_paid_sol"] = float(slot.get("fees_paid_sol", 0.0)) + actual_total_fee
                    slot["cycles_completed"] = int(slot.get("cycles_completed", 0)) + 1
                    slot["last_action"] = f"SELL +{abs_drift:.2f}% -> 50/50"

                    total_alpha += net_step_alpha
                    total_fees_paid += actual_total_fee
                    cycles += 1
                    rebalanced_this_tick = True

                    trade_history.insert(
                        0,
                        {
                            "id": f"rebal_sell_{int(now * 1000)}_{sym}_{cycles}",
                            "time": now,
                            "type": "SHANNON_SELL_EXCESS",
                            "symbol": sym,
                            "action": f"Sell Excess {sym}: -{tokens_to_sell:,.2f} {sym} -> +{net_sol_out:.4f} SOL",
                            "tranche_sol": round(gross_sol_out, 4),
                            "tokens_traded": round(tokens_to_sell, 4),
                            "ratio": curr_ratio,
                            "net_profit_sol": round(net_step_alpha, 6),
                            "reason": f"Drift +{abs_drift:.2f}% (Price +{abs(price_chg_ref_pct):.1f}%) >= {band_pct}% Band -> Restored 50/50",
                        },
                    )
                else:
                    # TOKEN DROPPED -> Token Kaffa < 50% -> Spend excess SOL Cash to buy cheap tokens
                    if cash_val >= delta_sol:
                        actual_dex_fee = delta_sol * DEX_FEE_RATE
                        net_sol_in = delta_sol - actual_dex_fee
                        tokens_bought = net_sol_in / curr_ratio
                        actual_total_fee = actual_dex_fee + SOL_TX_GAS_FEE

                        cash_val -= delta_sol
                        tokens_held += tokens_bought
                        gas_reserve -= SOL_TX_GAS_FEE

                        net_step_alpha = max(0.0, gross_step_alpha - actual_total_fee)
                        slot["slot_cash"] = cash_val
                        slot["tokens_held"] = tokens_held
                        slot["last_rebal_ratio"] = curr_ratio
                        slot["harvested_alpha_sol"] = float(slot.get("harvested_alpha_sol", 0.0)) + net_step_alpha
                        slot["fees_paid_sol"] = float(slot.get("fees_paid_sol", 0.0)) + actual_total_fee
                        slot["cycles_completed"] = int(slot.get("cycles_completed", 0)) + 1
                        slot["last_action"] = f"BUY -{abs_drift:.2f}% -> 50/50"

                        total_alpha += net_step_alpha
                        total_fees_paid += actual_total_fee
                        cycles += 1
                        rebalanced_this_tick = True

                        trade_history.insert(
                            0,
                            {
                                "id": f"rebal_buy_{int(now * 1000)}_{sym}_{cycles}",
                                "time": now,
                                "type": "SHANNON_BUY_DIP",
                                "symbol": sym,
                                "action": f"Buy Discount {sym}: -{delta_sol:.4f} SOL -> +{tokens_bought:,.2f} {sym}",
                                "tranche_sol": round(delta_sol, 4),
                                "tokens_traded": round(tokens_bought, 4),
                                "ratio": curr_ratio,
                                "net_profit_sol": round(net_step_alpha, 6),
                                "reason": f"Drift -{abs_drift:.2f}% (Price -{abs(price_chg_ref_pct):.1f}%) <= -{band_pct}% Band -> Restored 50/50",
                            },
                        )
            else:
                fee_blocked_this_tick = True

            # Recompute post-rebalance weights at the current live price
            token_val = tokens_held * curr_ratio
            slot_equity = cash_val + token_val
            w_cash = (cash_val / slot_equity) * 100.0 if slot_equity > 0 else 50.0
            w_token = (token_val / slot_equity) * 100.0 if slot_equity > 0 else 50.0
            drift = w_token - 50.0
            abs_drift = abs(drift)
            ref_ratio = float(slot.get("last_rebal_ratio") or curr_ratio)
            price_chg_ref_pct = ((curr_ratio - ref_ratio) / ref_ratio) * 100.0 if ref_ratio > 0 else 0.0

        # Persist updated display metrics on slot (keeping full precision on slot_cash & tokens_held)
        slot_cap = float(slot.get("slot_capital", BASKET_ALLOCATION_SOL))
        pnl_sol = slot_equity - slot_cap
        pnl_pct = (pnl_sol / slot_cap) * 100.0 if slot_cap > 0 else 0.0

        slot["token_sol_val"] = round(token_val, 6)
        slot["slot_equity"] = round(slot_equity, 6)
        slot["price_change_from_ref_pct"] = round(price_chg_ref_pct, 2)
        slot["weight_cash_pct"] = round(w_cash, 2)
        slot["weight_token_pct"] = round(w_token, 2)
        slot["drift_pct"] = round(drift, 2)
        slot["pnl_sol"] = round(pnl_sol, 6)
        slot["pnl_pct"] = round(pnl_pct, 2)

        progress_pct = min(100.0, round((abs_drift / band_pct) * 100.0, 1)) if band_pct > 0 else 0.0
        if rebalanced_this_tick:
            gate_status = "REBALANCED_50_50"
            status_text = f"REBALANCED -> 50.0% / 50.0% ({slot['cycles_completed']} cycles)"
        elif fee_blocked_this_tick:
            gate_status = "BLOCKED_FEE_DRAG"
            status_text = "HOLDING: Fee Gate protecting micro-swap"
        elif abs_drift >= band_pct * 0.75:
            gate_status = "NEAR_TRIGGER"
            status_text = f"APPROACHING BAND ({drift:+.2f}% / ±{band_pct}%)"
        else:
            gate_status = "IN_OPTIMAL_BAND"
            status_text = f"BALANCED IN BAND ({drift:+.2f}% / ±{band_pct}%)"

        scanned_status.append(
            {
                "symbol": sym,
                "pair": f"SOL / {sym}",
                "entry_ratio": float(slot.get("entry_ratio", curr_ratio)),
                "last_rebal_ratio": ref_ratio,
                "current_ratio": curr_ratio,
                "price_change_ref_pct": round(price_chg_ref_pct, 2),
                "weight_cash_pct": round(w_cash, 2),
                "weight_token_pct": round(w_token, 2),
                "drift_pct": round(drift, 2),
                "band_pct": band_pct,
                "progress_to_trigger_pct": progress_pct,
                "slot_equity": round(slot_equity, 5),
                "cycles_completed": int(slot.get("cycles_completed", 0)),
                "is_held": True,
                "gate_status": gate_status,
                "status_text": status_text,
            }
        )

    # -------------------------------------------------------------------------
    # STEP 3: PORTFOLIO AGGREGATION & STATIC 50/50 HODL BENCHMARK COMPARISON
    # -------------------------------------------------------------------------
    total_basket_cash = sum(float(s["slot_cash"]) for s in active_slots.values())
    total_token_val = sum(float(s["tokens_held"]) * float(s["current_ratio"]) for s in active_slots.values())
    total_slots_equity = total_basket_cash + total_token_val

    total_liquid_sol = gas_reserve + unallocated_cash + total_basket_cash
    total_equity = gas_reserve + unallocated_cash + total_slots_equity

    # Exact Static 50/50 Buy-and-Hold Benchmark (same initial tokens & initial cash, 0 rebalances)
    hodl_slots_equity = sum(
        float(s.get("initial_cash", s["slot_cash"]))
        + float(s.get("initial_tokens", s["tokens_held"])) * float(s["current_ratio"])
        for s in active_slots.values()
    )
    hodl_benchmark_sol = initial_gas_after_init + unallocated_cash + hodl_slots_equity
    rebalance_surplus_sol = total_equity - hodl_benchmark_sol

    initial_cap = float(state.get("initial_capital_sol", INITIAL_CAPITAL_SOL))
    total_profit_sol = total_equity - initial_cap
    total_profit_pct = (total_profit_sol / initial_cap) * 100.0 if initial_cap > 0 else 0.0

    state["gas_reserve_sol"] = round(gas_reserve, 6)
    state["initial_gas_after_init_sol"] = round(initial_gas_after_init, 6)
    state["unallocated_cash_sol"] = round(unallocated_cash, 6)
    state["central_cash_sol"] = round(total_liquid_sol, 6)
    state["total_basket_cash_sol"] = round(total_basket_cash, 6)
    state["total_liquid_sol"] = round(total_liquid_sol, 6)
    state["total_token_val_sol"] = round(total_token_val, 6)
    state["current_balance_sol"] = round(total_equity, 6)
    state["hodl_benchmark_sol"] = round(hodl_benchmark_sol, 6)
    state["rebalance_surplus_sol"] = round(rebalance_surplus_sol, 6)
    state["total_harvested_alpha_sol"] = round(total_alpha, 6)
    state["total_fees_paid_sol"] = round(total_fees_paid, 6)
    state["total_profit_sol"] = round(total_profit_sol, 6)
    state["total_profit_pct"] = round(total_profit_pct, 2)
    state["active_slots"] = active_slots
    state["active_slots_count"] = len(active_slots)
    state["total_cycles_completed"] = cycles
    state["scanned_pairs_status"] = scanned_status
    state["trade_history"] = trade_history[:80]

    save_demo_state(state)
    return state
