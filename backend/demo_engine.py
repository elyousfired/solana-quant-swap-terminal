"""
Solana Quant Swap Terminal - Pure Claude Shannon 6-Basket 50/50 + 15 Cross-Pair Triangular Engine
Implements authentic Claude Shannon's Demon (MIT, 1960s) & Thomas Cover's Constant Rebalanced
Portfolios across:
  - 6 Direct SOL / Token 50/50 Baskets (JUP, RAY, JTO, KMNO, MET, PUMP)
  - 15 Cross-Token Pairs (N*(N-1)/2 = 15 direct Token A -> Token B rotation channels)

Execution Priority Waterfall (شلال الأسبقية الثلاثي — Zero Conflict Architecture):
  - Stage 1 (Triangle Cash-Out to SOL):
      If a basket previously accumulated cheap tokens via Cross-Swap (cross_buy_streak > 0) and
      rebounds to Drift >= +1.0% against SOL, it immediately closes the 3rd leg of the triangle
      (Token B -> SOL Cash) and resets cross_buy_streak = 0.
  - Stage 2 (Priority #1 — 15-Pair Direct Cross-Swap Token A -> Token B):
      Scans all 15 relative pairs for opposite tilts (Drift_A >= +0.45% and Drift_B <= -0.45%)
      with Spread Drift (Drift_A - Drift_B) >= 1.10% and streak_B < 2.
      Executes a 1-hop direct swap (Token A -> Token B) for delta_swap = min(V_A - C_A, C_B - V_B),
      saving 50% of swap & gas fees while filling Basket B at the bottom.
  - Stage 3 (Priority #2 — Residual & Standalone Direct SOL Rebalance |Drift| >= 1.0%):
      Re-reads all 6 basket scales immediately in the same tick:
        * Standalone moves (no opposite partner, e.g. PUMP +15% alone) rebalance directly with SOL.
        * Residual Drift (e.g. KMNO had +0.0073 SOL excess, gave 0.0019 SOL to MET in Priority #1,
          and still has +0.0054 SOL residual excess >= +1.0% drift) sells the remaining excess
          directly into SOL Cash in the very same tick!
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

REBALANCE_BAND_PCT = 0.60         # Direct SOL/Token Drift Band: |w_token - 50%| >= 0.60% (~2.4% price move)
CROSS_SPREAD_BAND_PCT = 0.55      # 15-Pair Cross-Token Spread Band: (Drift_A - Drift_B) >= 0.55% (~2.2% spread)
CROSS_MIN_TILT_PCT = 0.25         # Overweight Kaffa A minimum tilt: Drift_A >= +0.25%
CROSS_MIN_LOW_TILT_PCT = 0.05     # Underweight Kaffa B minimum tilt: Drift_B <= -0.05%
MAX_CROSS_BUY_STREAK = 2          # Anti-Bleed Cap: max 2 consecutive cross-buys into same token before bounce

DEX_FEE_RATE = 0.0015             # 0.15% realistic Jupiter DEX swap fee
SOL_TX_GAS_FEE = 0.000005         # 0.000005 SOL Solana network transaction fee
MIN_REBALANCE_SOL = 0.0005        # Minimum SOL/Token swap size floor in SOL
MIN_CROSS_SWAP_SOL = 0.00055      # Minimum Cross-Token swap size floor in SOL
MIN_GAS_FLOOR_SOL = 0.0010        # Minimum gas reserve floor in SOL

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
        "cross_spread_band_pct": CROSS_SPREAD_BAND_PCT,
        "cross_min_tilt_pct": CROSS_MIN_TILT_PCT,
        "cross_min_low_tilt_pct": CROSS_MIN_LOW_TILT_PCT,
        "max_cross_buy_streak": MAX_CROSS_BUY_STREAK,
        "basket_allocation_sol": BASKET_ALLOCATION_SOL,
        "gas_reserve_sol": INITIAL_GAS_RESERVE_SOL,
        "initial_gas_after_init_sol": INITIAL_GAS_RESERVE_SOL,
        "unallocated_cash_sol": DEPLOYABLE_CAPITAL_SOL,
        "central_cash_sol": INITIAL_GAS_RESERVE_SOL + DEPLOYABLE_CAPITAL_SOL,
        "initial_basket_cash_sol": round(DEPLOYABLE_CAPITAL_SOL * 0.50, 6),
        "total_basket_cash_sol": 0.0,
        "basket_sol_delta": 0.0,
        "basket_sol_delta_pct": 0.0,
        "sol_qty_history": [round(DEPLOYABLE_CAPITAL_SOL * 0.50, 5)],
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
        "total_cross_swaps": 0,
        "cross_pairs_status": [],
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


def _execute_sol_sell_excess(
    sym: str,
    slot: Dict[str, Any],
    curr_ratio: float,
    band_pct: float,
    gas_reserve: float,
    now: float,
    cycles: int,
    total_alpha: float,
    total_fees_paid: float,
    trade_history: List[Dict[str, Any]],
    reason_prefix: str = "Drift",
):
    """Helper to sell excess token value above 50% directly into the basket's SOL cash."""
    cash_val = float(slot["slot_cash"])
    tokens_held = float(slot["tokens_held"])
    token_val = tokens_held * curr_ratio
    slot_equity = cash_val + token_val
    if slot_equity <= 0 or curr_ratio <= 0 or token_val <= cash_val:
        return False, gas_reserve, cycles, total_alpha, total_fees_paid, False

    w_token = (token_val / slot_equity) * 100.0
    drift = w_token - 50.0
    abs_drift = abs(drift)
    if drift < band_pct:
        return False, gas_reserve, cycles, total_alpha, total_fees_paid, False

    ref_ratio = float(slot.get("last_rebal_ratio") or slot.get("entry_ratio") or curr_ratio)
    price_chg_ref_pct = ((curr_ratio - ref_ratio) / ref_ratio) * 100.0 if ref_ratio > 0 else 0.0

    delta_sol = (token_val - cash_val) / 2.0
    dex_fee = delta_sol * DEX_FEE_RATE
    total_fee = dex_fee + SOL_TX_GAS_FEE
    rel_move = max(abs(price_chg_ref_pct) / 100.0, (4.0 * abs_drift) / 100.0)
    gross_step_alpha = 0.5 * delta_sol * rel_move

    if delta_sol < MIN_REBALANCE_SOL or gas_reserve < MIN_GAS_FLOOR_SOL or total_fee >= gross_step_alpha:
        return False, gas_reserve, cycles, total_alpha, total_fees_paid, True

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
    slot["cross_buy_streak"] = 0
    slot["harvested_alpha_sol"] = float(slot.get("harvested_alpha_sol", 0.0)) + net_step_alpha
    slot["fees_paid_sol"] = float(slot.get("fees_paid_sol", 0.0)) + actual_total_fee
    slot["cycles_completed"] = int(slot.get("cycles_completed", 0)) + 1
    slot["last_action"] = f"SELL +{abs_drift:.2f}% -> 50/50"

    total_alpha += net_step_alpha
    total_fees_paid += actual_total_fee
    cycles += 1

    trade_history.insert(
        0,
        {
            "id": f"rebal_sell_{int(now * 1000)}_{sym}_{cycles}",
            "time": now,
            "type": "SHANNON_SELL_EXCESS",
            "symbol": sym,
            "action": f"Sell Excess {sym}: -{tokens_to_sell:,.4f} {sym} -> +{net_sol_out:.5f} SOL",
            "tranche_sol": round(gross_sol_out, 6),
            "tokens_traded": round(tokens_to_sell, 6),
            "ratio": curr_ratio,
            "net_profit_sol": round(net_step_alpha, 6),
            "reason": f"{reason_prefix} +{abs_drift:.2f}% (Price +{abs(price_chg_ref_pct):.2f}%) >= {band_pct}% Band -> Restored 50/50",
        },
    )
    return True, gas_reserve, cycles, total_alpha, total_fees_paid, False


def evaluate_demo_tick(
    live_pairs: List[Dict[str, Any]],
    sol_usd: float,
    client_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes one live tick of the Pure Claude Shannon 6-Basket 50/50 + 15 Cross-Pair Triangular Engine
    using the 3-Stage Execution Priority Waterfall:
      - Stage 1: Triangle Cash-Out into SOL (for cross-loaded baskets with streak > 0 that bounced >= +1.0%).
      - Stage 2 (Priority #1): 15 Cross-Token Pairs Direct Swap (Token A -> Token B) for opposite tilts.
      - Stage 3 (Priority #2): Residual & Standalone Direct SOL Rebalancing (|Drift| >= 1.0%).
    """
    if _is_valid_strategy_state(client_state):
        state = client_state
    else:
        state = load_demo_state()

    if sol_usd and sol_usd > 0:
        state["sol_price_usd"] = round(float(sol_usd), 4)

    if not state.get("is_running", False):
        return state

    now = time.time()
    state["last_tick_time"] = now

    band_pct = REBALANCE_BAND_PCT
    cross_band_pct = CROSS_SPREAD_BAND_PCT
    cross_min_tilt = CROSS_MIN_TILT_PCT
    cross_min_low_tilt = CROSS_MIN_LOW_TILT_PCT
    max_streak = MAX_CROSS_BUY_STREAK

    state["rebalance_band_pct"] = band_pct
    state["cross_spread_band_pct"] = cross_band_pct
    state["cross_min_tilt_pct"] = cross_min_tilt
    state["cross_min_low_tilt_pct"] = cross_min_low_tilt
    state["max_cross_buy_streak"] = max_streak

    gas_reserve = float(state.get("gas_reserve_sol", INITIAL_GAS_RESERVE_SOL))
    initial_gas_after_init = float(state.get("initial_gas_after_init_sol", INITIAL_GAS_RESERVE_SOL))
    unallocated_cash = float(state.get("unallocated_cash_sol", 0.0))
    active_slots: Dict[str, Dict[str, Any]] = state.get("active_slots", {})
    trade_history: List[Dict[str, Any]] = state.get("trade_history", [])
    cycles = int(state.get("total_cycles_completed", 0))
    cross_swaps = int(state.get("total_cross_swaps", 0))
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
        tok_usd = float(p_data.get("base_usd", 0.0)) or (curr_ratio * float(sol_usd or 95.5))

        active_slots[sym] = {
            "token_symbol": sym,
            "pair": f"SOL / {sym}",
            "slot_capital": basket_cap,
            "initial_cash": cash_half,
            "initial_tokens": tokens_bought,
            "slot_cash": cash_half,
            "tokens_held": tokens_bought,
            "token_qty_delta": 0.0,
            "token_qty_delta_pct": 0.0,
            "qty_history": [round(tokens_bought, 6), round(tokens_bought, 6)],
            "token_sol_val": round(net_token_sol, 6),
            "slot_equity": round(slot_eq, 6),
            "entry_ratio": curr_ratio,
            "last_rebal_ratio": curr_ratio,
            "current_ratio": curr_ratio,
            "token_usd": tok_usd,
            "price_change_from_ref_pct": 0.0,
            "weight_cash_pct": round(w_cash, 2),
            "weight_token_pct": round(w_tok, 2),
            "drift_pct": round(w_tok - 50.0, 2),
            "pnl_sol": round(slot_eq - basket_cap, 6),
            "pnl_pct": round(((slot_eq - basket_cap) / basket_cap) * 100.0, 2),
            "harvested_alpha_sol": 0.0,
            "fees_paid_sol": round(entry_fee_total, 6),
            "cycles_completed": 0,
            "cross_swaps_count": 0,
            "cross_buy_streak": 0,
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
                "action": f"Basket {sym} 50/50: {cash_half:.4f} SOL Cash + {tokens_bought:,.4f} {sym}",
                "tranche_sol": round(token_half_gross, 6),
                "tokens_traded": round(tokens_bought, 6),
                "ratio": curr_ratio,
                "net_profit_sol": round(-entry_fee_total, 6),
                "reason": f"Equal 1/6 Basket Setup ({basket_cap:.4f} SOL -> 50% SOL / 50% {sym})",
            },
        )

    # Update live exchange rates across all 6 baskets
    for sym in BASKET_TOKENS:
        slot = active_slots.get(sym)
        if not slot:
            continue
        p_data = pairs_by_base.get(sym)
        if p_data and float(p_data.get("current_ratio", 0.0)) > 0:
            slot["current_ratio"] = float(p_data["current_ratio"])
            if float(p_data.get("base_usd", 0.0)) > 0:
                slot["token_usd"] = float(p_data["base_usd"])
            else:
                slot["token_usd"] = float(slot["current_ratio"]) * float(sol_usd or 95.5)

    rebalanced_sol_this_tick = set()
    fee_blocked_sol_this_tick = set()
    used_in_cross_this_tick = set()
    executed_cross_pair_keys = set()
    any_rebalanced_this_tick = False

    # -------------------------------------------------------------------------
    # STAGE 1: TRIANGLE CASH-OUT INTO SOL (Leg 3 of SOL -> A -> B -> SOL)
    # Any basket with cross_buy_streak > 0 that bounced >= +1.0% harvests into SOL first
    # -------------------------------------------------------------------------
    for sym in BASKET_TOKENS:
        slot = active_slots.get(sym)
        if not slot or int(slot.get("cross_buy_streak", 0)) <= 0:
            continue
        curr_ratio = float(slot["current_ratio"])
        did_sell, gas_reserve, cycles, total_alpha, total_fees_paid, blocked = _execute_sol_sell_excess(
            sym=sym,
            slot=slot,
            curr_ratio=curr_ratio,
            band_pct=band_pct,
            gas_reserve=gas_reserve,
            now=now,
            cycles=cycles,
            total_alpha=total_alpha,
            total_fees_paid=total_fees_paid,
            trade_history=trade_history,
            reason_prefix="Triangle Cash-Out Drift",
        )
        if did_sell:
            rebalanced_sol_this_tick.add(sym)
            any_rebalanced_this_tick = True
        elif blocked:
            fee_blocked_sol_this_tick.add(sym)

    # -------------------------------------------------------------------------
    # STAGE 2 (PRIORITY #1): 15-PAIR DIRECT CROSS-SWAP (Token A -> Token B)
    # Matches overweight Token A with underweight Token B in 1 single hop (50% fee saved)
    # -------------------------------------------------------------------------
    candidate_cross_pairs: List[Dict[str, Any]] = []
    present_syms = [s for s in BASKET_TOKENS if s in active_slots]

    for i in range(len(present_syms)):
        for j in range(i + 1, len(present_syms)):
            s1, s2 = present_syms[i], present_syms[j]
            slot1, slot2 = active_slots[s1], active_slots[s2]
            r1, r2 = float(slot1["current_ratio"]), float(slot2["current_ratio"])
            if r1 <= 0 or r2 <= 0:
                continue

            c1, v1 = float(slot1["slot_cash"]), float(slot1["tokens_held"]) * r1
            c2, v2 = float(slot2["slot_cash"]), float(slot2["tokens_held"]) * r2
            eq1, eq2 = c1 + v1, c2 + v2
            if eq1 <= 0 or eq2 <= 0:
                continue

            d1 = ((v1 / eq1) * 100.0) - 50.0
            d2 = ((v2 / eq2) * 100.0) - 50.0

            if d1 >= d2:
                high_sym, low_sym = s1, s2
                d_high, d_low = d1, d2
            else:
                high_sym, low_sym = s2, s1
                d_high, d_low = d2, d1

            spread_drift = d_high - d_low
            streak_low = int(active_slots[low_sym].get("cross_buy_streak", 0))

            if (d_high >= cross_min_tilt) and (d_low <= -cross_min_low_tilt) and (spread_drift >= cross_band_pct) and (streak_low < max_streak):
                candidate_cross_pairs.append(
                    {
                        "high_sym": high_sym,
                        "low_sym": low_sym,
                        "drift_high_pct": round(d_high, 2),
                        "drift_low_pct": round(d_low, 2),
                        "spread_drift_pct": round(spread_drift, 2),
                    }
                )

    candidate_cross_pairs.sort(key=lambda x: x["spread_drift_pct"], reverse=True)

    for cand in candidate_cross_pairs:
        sym_a = cand["high_sym"]
        sym_b = cand["low_sym"]
        if sym_a in used_in_cross_this_tick or sym_b in used_in_cross_this_tick:
            continue

        slot_a = active_slots[sym_a]
        slot_b = active_slots[sym_b]
        ratio_a = float(slot_a["current_ratio"])
        ratio_b = float(slot_b["current_ratio"])
        cash_a = float(slot_a["slot_cash"])
        cash_b = float(slot_b["slot_cash"])
        tok_a = float(slot_a["tokens_held"])
        tok_b = float(slot_b["tokens_held"])
        val_a = tok_a * ratio_a
        val_b = tok_b * ratio_b

        excess_a_sol = max(0.0, val_a - cash_a)
        deficit_b_sol = max(0.0, cash_b - val_b)
        target_b_capacity = max(deficit_b_sol, MIN_CROSS_SWAP_SOL)
        delta_swap_sol = min(excess_a_sol, target_b_capacity)

        if delta_swap_sol < MIN_CROSS_SWAP_SOL or gas_reserve < MIN_GAS_FLOOR_SOL:
            continue

        actual_dex_fee = delta_swap_sol * DEX_FEE_RATE
        actual_total_fee = actual_dex_fee + SOL_TX_GAS_FEE

        spread_drift = float(cand["spread_drift_pct"])
        rel_spread_move = (4.0 * spread_drift) / 100.0
        gross_cross_alpha = 0.5 * delta_swap_sol * rel_spread_move

        if actual_total_fee >= gross_cross_alpha:
            continue

        tokens_a_sold = min(tok_a, delta_swap_sol / ratio_a)
        gross_sol_equiv = tokens_a_sold * ratio_a
        net_sol_equiv = gross_sol_equiv - actual_dex_fee
        tokens_b_bought = net_sol_equiv / ratio_b

        new_tok_a = tok_a - tokens_a_sold
        new_tok_b = tok_b + tokens_b_bought
        slot_a["tokens_held"] = new_tok_a
        slot_b["tokens_held"] = new_tok_b
        gas_reserve -= SOL_TX_GAS_FEE

        net_cross_alpha = max(0.0, gross_cross_alpha - actual_total_fee)

        # Check remaining drift on A and B after Cross-Swap; if within band, update last_rebal_ratio
        # (If A still has a large Residual Drift >= band_pct, Stage 3 will harvest it into SOL Cash!)
        new_val_a = new_tok_a * ratio_a
        new_eq_a = cash_a + new_val_a
        rem_drift_a = abs(((new_val_a / new_eq_a) * 100.0) - 50.0) if new_eq_a > 0 else 0.0
        if rem_drift_a < band_pct:
            slot_a["last_rebal_ratio"] = ratio_a

        new_val_b = new_tok_b * ratio_b
        new_eq_b = cash_b + new_val_b
        rem_drift_b = abs(((new_val_b / new_eq_b) * 100.0) - 50.0) if new_eq_b > 0 else 0.0
        if rem_drift_b < band_pct:
            slot_b["last_rebal_ratio"] = ratio_b

        slot_a["cross_buy_streak"] = 0
        slot_b["cross_buy_streak"] = int(slot_b.get("cross_buy_streak", 0)) + 1

        slot_a["cross_swaps_count"] = int(slot_a.get("cross_swaps_count", 0)) + 1
        slot_b["cross_swaps_count"] = int(slot_b.get("cross_swaps_count", 0)) + 1
        slot_a["cycles_completed"] = int(slot_a.get("cycles_completed", 0)) + 1
        slot_b["cycles_completed"] = int(slot_b.get("cycles_completed", 0)) + 1

        slot_a["harvested_alpha_sol"] = float(slot_a.get("harvested_alpha_sol", 0.0)) + (net_cross_alpha * 0.5)
        slot_b["harvested_alpha_sol"] = float(slot_b.get("harvested_alpha_sol", 0.0)) + (net_cross_alpha * 0.5)
        slot_a["fees_paid_sol"] = float(slot_a.get("fees_paid_sol", 0.0)) + (actual_total_fee * 0.5)
        slot_b["fees_paid_sol"] = float(slot_b.get("fees_paid_sol", 0.0)) + (actual_total_fee * 0.5)

        slot_a["last_action"] = f"CROSS {sym_a}->{sym_b} (-{tokens_a_sold:,.4f})"
        slot_b["last_action"] = f"CROSS {sym_a}->{sym_b} (+{tokens_b_bought:,.4f})"

        total_alpha += net_cross_alpha
        total_fees_paid += actual_total_fee
        cycles += 1
        cross_swaps += 1
        any_rebalanced_this_tick = True
        used_in_cross_this_tick.add(sym_a)
        used_in_cross_this_tick.add(sym_b)
        executed_cross_pair_keys.add(tuple(sorted([sym_a, sym_b])))

        trade_history.insert(
            0,
            {
                "id": f"cross_{int(now * 1000)}_{sym_a}_{sym_b}_{cycles}",
                "time": now,
                "type": "SHANNON_CROSS_SWAP",
                "symbol": f"{sym_a}->{sym_b}",
                "action": f"Cross-Swap {sym_a} -> {sym_b}: -{tokens_a_sold:,.4f} {sym_a} -> +{tokens_b_bought:,.4f} {sym_b}",
                "tranche_sol": round(gross_sol_equiv, 6),
                "tokens_traded": round(tokens_b_bought, 6),
                "ratio": round(ratio_a / ratio_b, 10) if ratio_b > 0 else ratio_a,
                "net_profit_sol": round(net_cross_alpha, 6),
                "reason": (
                    f"Priority #1 Cross Spread +{spread_drift:.2f}% ({sym_a} {cand['drift_high_pct']:+.2f}% vs "
                    f"{sym_b} {cand['drift_low_pct']:+.2f}%) | Streak {slot_b['cross_buy_streak']}/{max_streak}"
                ),
            },
        )

    # -------------------------------------------------------------------------
    # STAGE 3 (PRIORITY #2): RESIDUAL & STANDALONE DIRECT SOL REBALANCE (|Drift| >= 1.0%)
    # Re-reads all 6 baskets after Priority #1 and harvests any residual or standalone drift into SOL
    # -------------------------------------------------------------------------
    for sym in BASKET_TOKENS:
        slot = active_slots.get(sym)
        if not slot:
            continue

        curr_ratio = float(slot["current_ratio"])
        cash_val = float(slot["slot_cash"])
        tokens_held = float(slot["tokens_held"])
        token_val = tokens_held * curr_ratio
        slot_equity = cash_val + token_val

        w_token = (token_val / slot_equity) * 100.0 if slot_equity > 0 else 50.0
        drift = w_token - 50.0
        abs_drift = abs(drift)

        if abs_drift < band_pct or slot_equity <= 0 or curr_ratio <= 0:
            continue

        ref_ratio = float(slot.get("last_rebal_ratio") or slot.get("entry_ratio") or curr_ratio)
        price_chg_ref_pct = ((curr_ratio - ref_ratio) / ref_ratio) * 100.0 if ref_ratio > 0 else 0.0
        reason_lbl = "Residual Drift" if sym in used_in_cross_this_tick else "Drift"

        if drift > 0:
            did_sell, gas_reserve, cycles, total_alpha, total_fees_paid, blocked = _execute_sol_sell_excess(
                sym=sym,
                slot=slot,
                curr_ratio=curr_ratio,
                band_pct=band_pct,
                gas_reserve=gas_reserve,
                now=now,
                cycles=cycles,
                total_alpha=total_alpha,
                total_fees_paid=total_fees_paid,
                trade_history=trade_history,
                reason_prefix=reason_lbl,
            )
            if did_sell:
                rebalanced_sol_this_tick.add(sym)
                any_rebalanced_this_tick = True
            elif blocked:
                fee_blocked_sol_this_tick.add(sym)
        else:
            delta_sol = (cash_val - token_val) / 2.0
            dex_fee = delta_sol * DEX_FEE_RATE
            total_fee = dex_fee + SOL_TX_GAS_FEE
            rel_move = max(abs(price_chg_ref_pct) / 100.0, (4.0 * abs_drift) / 100.0)
            gross_step_alpha = 0.5 * delta_sol * rel_move

            if (
                delta_sol >= MIN_REBALANCE_SOL
                and gas_reserve >= MIN_GAS_FLOOR_SOL
                and total_fee < gross_step_alpha
                and cash_val >= delta_sol
            ):
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
                rebalanced_sol_this_tick.add(sym)
                any_rebalanced_this_tick = True

                trade_history.insert(
                    0,
                    {
                        "id": f"rebal_buy_{int(now * 1000)}_{sym}_{cycles}",
                        "time": now,
                        "type": "SHANNON_BUY_DIP",
                        "symbol": sym,
                        "action": f"Buy Discount {sym}: -{delta_sol:.5f} SOL -> +{tokens_bought:,.4f} {sym}",
                        "tranche_sol": round(delta_sol, 6),
                        "tokens_traded": round(tokens_bought, 6),
                        "ratio": curr_ratio,
                        "net_profit_sol": round(net_step_alpha, 6),
                        "reason": f"{reason_lbl} -{abs_drift:.2f}% (Price -{abs(price_chg_ref_pct):.2f}%) <= -{band_pct}% Band -> Restored 50/50",
                    },
                )
            else:
                fee_blocked_sol_this_tick.add(sym)

    # -------------------------------------------------------------------------
    # STAGE 4: COMPUTE FINAL 6-BASKET & 15-CROSS-PAIR LIVE TELEMETRY
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
                    "token_usd": float(p_data.get("base_usd", 0.0)) if p_data else 0.0,
                    "price_change_ref_pct": 0.0,
                    "weight_cash_pct": 50.0,
                    "weight_token_pct": 50.0,
                    "drift_pct": 0.0,
                    "band_pct": band_pct,
                    "progress_to_trigger_pct": 0.0,
                    "slot_equity": 0.0,
                    "cycles_completed": 0,
                    "cross_buy_streak": 0,
                    "is_held": False,
                    "gate_status": "AWAITING_FEED",
                    "status_text": "Waiting for live Jupiter price feed",
                }
            )
            continue

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

        rebalanced_this_tick = (sym in rebalanced_sol_this_tick) or (sym in used_in_cross_this_tick)
        fee_blocked_this_tick = sym in fee_blocked_sol_this_tick

        init_tok = float(slot.get("initial_tokens", tokens_held))
        tok_delta = tokens_held - init_tok
        tok_delta_pct = ((tok_delta / init_tok) * 100.0) if init_tok > 0 else 0.0
        slot["token_qty_delta"] = round(tok_delta, 6)
        slot["token_qty_delta_pct"] = round(tok_delta_pct, 2)

        q_hist = list(slot.get("qty_history") or [])
        if not q_hist:
            q_hist = [round(init_tok, 6), round(tokens_held, 6)]
        elif rebalanced_this_tick or len(q_hist) < 12 or abs(q_hist[-1] - round(tokens_held, 6)) > 1e-6:
            q_hist.append(round(tokens_held, 6))
        slot["qty_history"] = q_hist[-30:]

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
        if sym in rebalanced_sol_this_tick:
            gate_status = "REBALANCED_50_50"
            status_text = f"REBALANCED -> 50.0% / 50.0% ({slot['cycles_completed']} cycles)"
        elif sym in used_in_cross_this_tick:
            gate_status = "CROSS_ROTATED"
            status_text = f"CROSS-SWAP 50/50 ({slot.get('last_action', 'ROTATED')})"
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
                "token_usd": float(slot.get("token_usd", 0.0)),
                "price_change_ref_pct": round(price_chg_ref_pct, 2),
                "weight_cash_pct": round(w_cash, 2),
                "weight_token_pct": round(w_token, 2),
                "drift_pct": round(drift, 2),
                "band_pct": band_pct,
                "progress_to_trigger_pct": progress_pct,
                "slot_equity": round(slot_equity, 6),
                "cycles_completed": int(slot.get("cycles_completed", 0)),
                "cross_buy_streak": int(slot.get("cross_buy_streak", 0)),
                "is_held": True,
                "gate_status": gate_status,
                "status_text": status_text,
            }
        )

    # Build final post-tick 15 cross-pair telemetry sorted by spread_drift_pct descending
    all_cross_pairs_info: List[Dict[str, Any]] = []
    for i in range(len(present_syms)):
        for j in range(i + 1, len(present_syms)):
            s1, s2 = present_syms[i], present_syms[j]
            slot1, slot2 = active_slots[s1], active_slots[s2]
            d1 = float(slot1.get("drift_pct", 0.0))
            d2 = float(slot2.get("drift_pct", 0.0))

            if d1 >= d2:
                high_sym, low_sym = s1, s2
                d_high, d_low = d1, d2
            else:
                high_sym, low_sym = s2, s1
                d_high, d_low = d2, d1

            spread_drift = d_high - d_low
            rel_price_spread_pct = spread_drift * 4.0
            streak_low = int(active_slots[low_sym].get("cross_buy_streak", 0))
            is_opposite_tilt = (d_high >= cross_min_tilt) and (d_low <= -cross_min_low_tilt)
            is_spread_ready = spread_drift >= cross_band_pct
            is_bleed_safe = streak_low < max_streak
            pair_key = tuple(sorted([s1, s2]))

            if pair_key in executed_cross_pair_keys:
                p_status = "EXECUTED_CROSS_SWAP"
            elif is_opposite_tilt and is_spread_ready and is_bleed_safe:
                p_status = "READY_CROSS_SWAP"
            elif is_opposite_tilt and is_spread_ready and not is_bleed_safe:
                p_status = "BLEED_CAP_HOLD"
            elif is_opposite_tilt:
                p_status = "WATCHING_SPREAD"
            else:
                p_status = "NEUTRAL"

            all_cross_pairs_info.append(
                {
                    "pair": f"{high_sym} -> {low_sym}",
                    "high_sym": high_sym,
                    "low_sym": low_sym,
                    "drift_high_pct": round(d_high, 2),
                    "drift_low_pct": round(d_low, 2),
                    "spread_drift_pct": round(spread_drift, 2),
                    "rel_price_spread_pct": round(rel_price_spread_pct, 2),
                    "streak_low": streak_low,
                    "max_streak": max_streak,
                    "is_opposite_tilt": is_opposite_tilt,
                    "status": p_status,
                }
            )

    all_cross_pairs_info.sort(key=lambda x: (1 if x["status"] == "EXECUTED_CROSS_SWAP" else 0, x["spread_drift_pct"]), reverse=True)

    # -------------------------------------------------------------------------
    # STEP 5: PORTFOLIO AGGREGATION & STATIC 50/50 HODL BENCHMARK COMPARISON
    # -------------------------------------------------------------------------
    initial_basket_cash = sum(float(s.get("initial_cash", 0.08)) for s in active_slots.values()) or round(DEPLOYABLE_CAPITAL_SOL * 0.50, 6)
    total_basket_cash = sum(float(s["slot_cash"]) for s in active_slots.values())
    basket_sol_delta = total_basket_cash - initial_basket_cash
    basket_sol_delta_pct = ((basket_sol_delta / initial_basket_cash) * 100.0) if initial_basket_cash > 0 else 0.0

    sol_hist = list(state.get("sol_qty_history") or [])
    if not sol_hist:
        sol_hist = [round(initial_basket_cash, 5), round(total_basket_cash, 5)]
    elif any_rebalanced_this_tick or len(sol_hist) < 12 or abs(sol_hist[-1] - round(total_basket_cash, 5)) > 1e-6:
        sol_hist.append(round(total_basket_cash, 5))
    sol_hist = sol_hist[-30:]

    total_token_val = sum(float(s["tokens_held"]) * float(s["current_ratio"]) for s in active_slots.values())
    total_slots_equity = total_basket_cash + total_token_val

    total_liquid_sol = gas_reserve + unallocated_cash + total_basket_cash
    total_equity = gas_reserve + unallocated_cash + total_slots_equity

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
    state["initial_basket_cash_sol"] = round(initial_basket_cash, 6)
    state["total_basket_cash_sol"] = round(total_basket_cash, 6)
    state["basket_sol_delta"] = round(basket_sol_delta, 6)
    state["basket_sol_delta_pct"] = round(basket_sol_delta_pct, 2)
    state["sol_qty_history"] = sol_hist
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
    state["total_cross_swaps"] = cross_swaps
    state["cross_pairs_status"] = all_cross_pairs_info
    state["scanned_pairs_status"] = scanned_status
    state["trade_history"] = trade_history[:80]

    save_demo_state(state)
    return state
