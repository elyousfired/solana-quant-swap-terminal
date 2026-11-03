"""
Automated Forensic Verification Suite for the 3-Stage Priority Waterfall Engine:
  - Stage 1: Triangle Cash-Out into SOL (cross-loaded basket with streak > 0 bouncing >= +1.0%)
  - Stage 2 (Priority #1): 15 Cross-Token Pairs Direct Swap (Token A -> Token B)
  - Stage 3 (Priority #2): Residual & Standalone Direct SOL Rebalancing (|Drift| >= 1.0%)
"""

from backend.demo_engine import (
    get_initial_state,
    evaluate_demo_tick,
    STRATEGY_ID,
)


def make_mock_pairs(multipliers=None):
    multipliers = multipliers or {}
    base_ratios = {
        "JUP": 0.00262,
        "RAY": 0.01750,
        "JTO": 0.00382,
        "KMNO": 0.000375,
        "MET": 0.00288,
        "PUMP": 0.000041,
    }
    pairs = []
    for sym, r in base_ratios.items():
        m = multipliers.get(sym, 1.0)
        pairs.append({
            "pair": f"SOL / {sym}",
            "base_token": sym,
            "quote_token": "SOL",
            "current_ratio": r * m,
            "z_score": 1.85,
            "target_yield_pct": 0.0,
        })
    return pairs


def run_tests():
    print("=== TEST 1: Initial 6-Basket Simultaneous 50/50 Setup ===")
    state = get_initial_state()
    assert state["strategy"] == STRATEGY_ID
    assert state["rebalance_band_pct"] == 1.0
    assert state["cross_spread_band_pct"] == 1.10

    state = evaluate_demo_tick(make_mock_pairs(), sol_usd=92.89, client_state=state)
    assert state["active_slots_count"] == 6
    assert len(state["cross_pairs_status"]) == 15
    jup_init_qty = state["active_slots"]["JUP"]["initial_tokens"]
    jto_init_qty = state["active_slots"]["JTO"]["initial_tokens"]
    print(f"  [OK] Initialized 6 Baskets + 15 Cross-Pairs | JTO Init: {jto_init_qty:.2f} | JUP Init: {jup_init_qty:.2f}")

    print("\n=== TEST 2: Small Isolated Move Inside Band (JUP +1.5% Only) ===")
    state = evaluate_demo_tick(make_mock_pairs({"JUP": 1.015}), sol_usd=92.89, client_state=state)
    assert state["total_cycles_completed"] == 0, "Should NOT rebalance on tiny isolated move"
    print("  [OK] JUP +1.5% isolated -> 0 Swaps")

    print("\n=== TEST 3: Priority #1 Direct Cross-Swap (JTO +3.0% vs JUP -3.0%) ===")
    state = evaluate_demo_tick(
        make_mock_pairs({"JTO": 1.030, "JUP": 0.970}),
        sol_usd=92.89,
        client_state=state,
    )
    assert state["total_cross_swaps"] == 1
    latest_tx = state["trade_history"][0]
    assert latest_tx["type"] == "SHANNON_CROSS_SWAP"
    assert state["active_slots"]["JUP"]["tokens_held"] > jup_init_qty
    assert state["active_slots"]["JTO"]["tokens_held"] < jto_init_qty
    print(f"  [OK] {latest_tx['type']} | {latest_tx['action']}")
    print(f"  [OK] {latest_tx['reason']}")

    print("\n=== TEST 4: Stage 1 Triangle Cash-Out into SOL (JUP Bounces to +1.5%, JTO Reverts to 1.00x) ===")
    state = evaluate_demo_tick(
        make_mock_pairs({"JTO": 1.000, "JUP": 1.015}),
        sol_usd=92.89,
        client_state=state,
    )
    sell_txs = [t for t in state["trade_history"] if t["type"] == "SHANNON_SELL_EXCESS" and t["symbol"] == "JUP"]
    assert len(sell_txs) >= 1, "Expected JUP bounce to close triangle into SOL cash!"
    assert state["total_basket_cash_sol"] > state["initial_basket_cash_sol"]
    assert state["active_slots"]["JUP"]["cross_buy_streak"] == 0
    print(f"  [OK] Triangle Closed into SOL: {sell_txs[0]['action']} | {sell_txs[0]['reason']}")
    print(f"  [OK] Total SOL in 6 Baskets: {state['initial_basket_cash_sol']:.5f} -> {state['total_basket_cash_sol']:.5f} SOL")

    print("\n=== TEST 5: Priority #1 Cross-Swap + Priority #2 Residual SOL Swap in SAME Tick ===")
    # KMNO jumps +12% (+2.75% drift, large excess ~0.0094 SOL), while MET dips -2.4% (-0.69% drift, small deficit ~0.0019 SOL).
    # In the SAME tick:
    #   1) Priority #1 executes Cross-Swap KMNO -> MET (fills MET deficit in 1 hop).
    #   2) Priority #2 immediately sees KMNO still has Residual Drift >= +1.0% and sells the remaining KMNO excess into SOL cash!
    prev_cross = state["total_cross_swaps"]
    state = evaluate_demo_tick(
        make_mock_pairs({"KMNO": 1.120, "MET": 0.976}),
        sol_usd=92.89,
        client_state=state,
    )
    assert state["total_cross_swaps"] == prev_cross + 1, "Expected Priority #1 Cross-Swap KMNO -> MET"
    kmno_residual_sell = [
        t for t in state["trade_history"][:2]
        if t["type"] == "SHANNON_SELL_EXCESS" and t["symbol"] == "KMNO" and "Residual Drift" in t["reason"]
    ]
    assert len(kmno_residual_sell) == 1, "Expected Priority #2 Residual Drift SELL on KMNO in the same tick!"
    print(f"  [OK] Priority #1 Executed: {state['trade_history'][1]['action']}")
    print(f"  [OK] Priority #2 Residual Executed in Same Tick: {kmno_residual_sell[0]['action']} ({kmno_residual_sell[0]['reason']})")

    print("\n=== TEST 6: Full Portfolio Mean-Reversion Back to 1.00x Baseline ===")
    state = evaluate_demo_tick(make_mock_pairs(), sol_usd=92.89, client_state=state)
    assert state["rebalance_surplus_sol"] > 0
    print(f"  [OK] Total Cycles Completed: {state['total_cycles_completed']} (Cross-Swaps: {state['total_cross_swaps']})")
    print(f"  [OK] Harvested Volatility Alpha: +{state['total_harvested_alpha_sol']:.6f} SOL")
    print(f"  [OK] Pure Realized Surplus vs Static 50/50 HODL (AFTER ALL FEES): +{state['rebalance_surplus_sol']:.6f} SOL")
    print("\nALL 6 PRIORITY WATERFALL & HOMOGENEITY TESTS PASSED 100%!")


if __name__ == "__main__":
    run_tests()
