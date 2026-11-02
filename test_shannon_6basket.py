"""
Automated Forensic Verification Suite for Pure Claude Shannon 6-Basket 50/50 Threshold Engine.
Verifies:
1. Immediate 6-basket simultaneous 50/50 deployment (0.04 SOL Gas + 6 x 0.16 SOL Baskets).
2. Zero Z-score dip blocking (enters pumping and flat tokens immediately at 50/50).
3. In-band noise immunity (|Drift| < 2.5% executes 0 swaps and burns 0 fees).
4. Pump breach (Drift >= +2.5%) sells exact excess token -> banks SOL -> restores 50.0/50.0 at new price.
5. Dump breach (Drift <= -2.5%) buys cheap token with basket SOL -> restores 50.0/50.0 at new price.
6. Round-trip oscillation yields positive net equity surplus over static 50/50 Buy-and-Hold after all fees.
"""

from backend.demo_engine import (
    get_initial_state,
    evaluate_demo_tick,
    BASKET_TOKENS,
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
            "z_score": 1.85,  # Positive Z-score: proves NO Z <= -1.4 dip blocker!
            "target_yield_pct": 0.0,
        })
    return pairs


def run_tests():
    print("=== TEST 1: Initial 6-Basket Simultaneous 50/50 Setup ===")
    state = get_initial_state()
    assert state["strategy"] == STRATEGY_ID

    state = evaluate_demo_tick(make_mock_pairs(), sol_usd=100.0, client_state=state)
    assert state["active_slots_count"] == 6, f"Expected 6 baskets, got {state['active_slots_count']}"
    assert abs(state["unallocated_cash_sol"]) < 1e-6, "All 0.96 SOL deployable capital must be allocated"
    assert abs(state["total_basket_cash_sol"] - 0.48) < 1e-4, f"Expected 0.48 SOL total basket cash, got {state['total_basket_cash_sol']}"

    for sym in BASKET_TOKENS:
        slot = state["active_slots"][sym]
        assert abs(slot["slot_cash"] - 0.08) < 1e-6
        assert abs(slot["weight_cash_pct"] - 50.04) < 0.2
        assert abs(slot["weight_token_pct"] - 49.96) < 0.2
        print(f"  [OK] {sym:4s} | Cash: {slot['slot_cash']:.4f} SOL | Token Val: {slot['token_sol_val']:.4f} SOL | Weights: {slot['weight_cash_pct']}% / {slot['weight_token_pct']}%")

    print("\n=== TEST 2: Small Price Move Inside ±2.5% Band (+4% Price -> +0.98% Drift) ===")
    state = evaluate_demo_tick(make_mock_pairs({"PUMP": 1.04}), sol_usd=100.0, client_state=state)
    assert state["total_cycles_completed"] == 0, "Should NOT rebalance inside ±2.5% drift band"
    pump_slot = state["active_slots"]["PUMP"]
    print(f"  [OK] PUMP +4% Price -> Drift: {pump_slot['drift_pct']:+.2f}% (< 2.5% Band) -> 0 Rebalances (Fee Protected)")

    print("\n=== TEST 3: Price Surge Breaching +2.5% Band (+15% Price on PUMP) ===")
    state = evaluate_demo_tick(make_mock_pairs({"PUMP": 1.15}), sol_usd=100.0, client_state=state)
    assert state["total_cycles_completed"] == 1, f"Expected 1 rebalance, got {state['total_cycles_completed']}"
    pump_slot = state["active_slots"]["PUMP"]
    assert pump_slot["slot_cash"] > 0.085, f"Cash should have increased from selling excess PUMP, got {pump_slot['slot_cash']}"
    assert abs(pump_slot["drift_pct"]) < 0.1, f"Post-rebalance drift must return to ~0.0%, got {pump_slot['drift_pct']}"
    latest_tx = state["trade_history"][0]
    assert latest_tx["type"] == "SHANNON_SELL_EXCESS"
    print(f"  [OK] {latest_tx['action']}")
    print(f"  [OK] Post-Sell Scale: SOL {pump_slot['weight_cash_pct']}% / PUMP {pump_slot['weight_token_pct']}% | New Cash: {pump_slot['slot_cash']:.5f} SOL")

    print("\n=== TEST 4: Price Pullback Back to Baseline (1.00x on PUMP -> Breaches -2.5% Band) ===")
    state = evaluate_demo_tick(make_mock_pairs({"PUMP": 1.00}), sol_usd=100.0, client_state=state)
    assert state["total_cycles_completed"] == 2, f"Expected 2 rebalances, got {state['total_cycles_completed']}"
    pump_slot = state["active_slots"]["PUMP"]
    latest_tx = state["trade_history"][0]
    assert latest_tx["type"] == "SHANNON_BUY_DIP"
    assert abs(pump_slot["drift_pct"]) < 0.1, f"Post-rebalance drift must return to ~0.0%, got {pump_slot['drift_pct']}"
    assert state["rebalance_surplus_sol"] > 0, f"Expected positive net surplus vs static 50/50 HODL, got {state['rebalance_surplus_sol']}"
    print(f"  [OK] {latest_tx['action']}")
    print(f"  [OK] Post-Buy Scale: SOL {pump_slot['weight_cash_pct']}% / PUMP {pump_slot['weight_token_pct']}%")
    print(f"  [OK] Pure Realized Surplus vs Static 50/50 HODL (AFTER ALL FEES): +{state['rebalance_surplus_sol']:.6f} SOL")
    print(f"  [OK] Total Harvested Volatility Alpha: +{state['total_harvested_alpha_sol']:.6f} SOL")
    print("\nALL 6-BASKET PURE SHANNON TESTS PASSED 100%!")


if __name__ == "__main__":
    run_tests()
