"""
Automated Forensic Verification Suite for Pure Claude Shannon 6-Basket 50/50 + 15 Cross-Pair Engine.
Verifies:
1. Immediate 6-basket simultaneous 50/50 deployment (0.04 SOL Gas + 6 x 0.16 SOL Baskets).
2. In-band noise immunity (single token +1.5% -> 0 swaps).
3. 15-Pair Cross-Token Rotation (JTO +3.0% vs JUP -3.0%): neither hits ±1.0% vs SOL alone,
   but their relative spread (+1.54% drift spread) triggers a direct 1-hop JTO ➔ JUP Cross-Swap!
4. Triangular Double-Dip into SOL: When JUP bounces back (+1.5% above initial entry), the extra
   accumulated JUP coins push Basket JUP >= +1.0% drift and harvest pure SOL cash!
5. Multi-pair volatility + mean-reversion yields positive net equity surplus over static 50/50 HODL.
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
    jup_init_qty = state["active_slots"]["JUP"]["initial_tokens"]
    jto_init_qty = state["active_slots"]["JTO"]["initial_tokens"]
    print(f"  [OK] Initialized 6 Baskets | JTO Init: {jto_init_qty:.2f} | JUP Init: {jup_init_qty:.2f}")

    print("\n=== TEST 2: Small Isolated Move Inside Band (JUP +1.5% Only) ===")
    state = evaluate_demo_tick(make_mock_pairs({"JUP": 1.015}), sol_usd=92.89, client_state=state)
    assert state["total_cycles_completed"] == 0, "Should NOT rebalance on tiny isolated move"
    print(f"  [OK] JUP +1.5% isolated -> 0 Swaps")

    print("\n=== TEST 3: 15-Pair Cross-Token Rotation (JTO +3.0% vs JUP -3.0%) ===")
    # Neither JTO (+3.0% -> +0.70% drift) nor JUP (-3.0% -> -0.84% drift) hits ±1.0% vs SOL alone!
    # But Spread Drift = 1.54% >= 1.10% -> Fires direct 1-hop JTO ➔ JUP Cross-Swap!
    state = evaluate_demo_tick(
        make_mock_pairs({"JTO": 1.030, "JUP": 0.970}),
        sol_usd=92.89,
        client_state=state,
    )
    assert state["total_cross_swaps"] == 1, f"Expected 1 cross-swap (JTO ➔ JUP), got {state['total_cross_swaps']}"
    latest_tx = state["trade_history"][0]
    assert latest_tx["type"] == "SHANNON_CROSS_SWAP"
    assert state["active_slots"]["JUP"]["tokens_held"] > jup_init_qty
    assert state["active_slots"]["JTO"]["tokens_held"] < jto_init_qty
    print(f"  [OK] {latest_tx['type']} | {latest_tx['action']}")
    print(f"  [OK] JUP Coins Accumulated: {jup_init_qty:.2f} -> {state['active_slots']['JUP']['tokens_held']:.2f} (+{state['active_slots']['JUP']['token_qty_delta']:.2f} JUP)")
    print(f"  [OK] JTO Coins Trimmed High: {jto_init_qty:.2f} -> {state['active_slots']['JTO']['tokens_held']:.2f} ({state['active_slots']['JTO']['token_qty_delta']:+.2f} JTO)")

    print("\n=== TEST 4: Triangular Double-Dip Harvest into SOL (JUP Bounces to +1.5%, JTO Reverts to 1.00x) ===")
    # Because JUP was pre-loaded with extra cheap coins at 0.97x, bouncing to 1.015x (+4.6% from dip)
    # pushes JUP basket drift >= +1.0% and harvests excess directly into pure SOL Cash!
    state = evaluate_demo_tick(
        make_mock_pairs({"JTO": 1.000, "JUP": 1.015}),
        sol_usd=92.89,
        client_state=state,
    )
    sell_txs = [t for t in state["trade_history"] if t["type"] == "SHANNON_SELL_EXCESS" and t["symbol"] == "JUP"]
    assert len(sell_txs) >= 1, "Expected JUP bounce to trigger SHANNON_SELL_EXCESS into SOL cash!"
    assert state["total_basket_cash_sol"] > state["initial_basket_cash_sol"], "Expected total basket SOL cash to increase!"
    print(f"  [OK] Double-Dip Harvested into SOL: {sell_txs[0]['action']}")
    print(f"  [OK] Total SOL in 6 Baskets: {state['initial_basket_cash_sol']:.5f} -> {state['total_basket_cash_sol']:.5f} SOL ({state['basket_sol_delta']:+.5f} SOL)")
    print(f"  [OK] JUP Streak Reset After SOL Harvest: {state['active_slots']['JUP']['cross_buy_streak']}/2")

    print("\n=== TEST 5: Multi-Pair Volatility Wave & Mean-Reversion Surplus ===")
    state = evaluate_demo_tick(
        make_mock_pairs({"KMNO": 1.093, "JTO": 0.951, "PUMP": 1.047, "JUP": 1.014, "RAY": 0.994, "MET": 0.976}),
        sol_usd=92.89,
        client_state=state,
    )
    state = evaluate_demo_tick(make_mock_pairs(), sol_usd=92.89, client_state=state)
    assert state["rebalance_surplus_sol"] > 0, f"Expected positive net surplus vs static 50/50 HODL, got {state['rebalance_surplus_sol']}"
    print(f"  [OK] Total Cycles Completed: {state['total_cycles_completed']} (including {state['total_cross_swaps']} Cross-Swaps)")
    print(f"  [OK] Harvested Volatility Alpha: +{state['total_harvested_alpha_sol']:.6f} SOL")
    print(f"  [OK] Pure Realized Surplus vs Static 50/50 HODL (AFTER ALL FEES): +{state['rebalance_surplus_sol']:.6f} SOL")
    print("\nALL 6-BASKET + 15 CROSS-PAIR TRIANGULAR TESTS PASSED 100%!")


if __name__ == "__main__":
    run_tests()
