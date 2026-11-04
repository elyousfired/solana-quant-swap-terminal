"""
Automated Verification Suite for Engine 5 (V2 Real Price-Action Execution):
Smart Maker & Dynamic DLMM Bin Engine (backend/as_maker_engine.py)
"""

from backend.as_maker_engine import (
    get_initial_as_state,
    evaluate_as_maker_tick,
    STRATEGY_ID,
)


def make_mock_pairs(multipliers=None):
    multipliers = multipliers or {}
    base_ratios = {
        "JUP": 0.00262000,
        "RAY": 0.01750000,
        "JTO": 0.00382000,
        "KMNO": 0.00037500,
        "MET": 0.00288000,
        "PUMP": 0.00004100,
    }
    pairs = []
    for sym, r in base_ratios.items():
        m = multipliers.get(sym, 1.0)
        pairs.append({
            "pair": f"SOL / {sym}",
            "base_token": sym,
            "quote_token": "SOL",
            "current_ratio": r * m,
            "base_usd": (r * m) * 84.50,
            "z_score": 1.40,
        })
    return pairs


def run_tests():
    print("=== TEST 1: 100% SOL Vault Initialization (Zero Blind Token Buying at T=0) ===")
    state = get_initial_as_state()
    assert state["strategy"] == STRATEGY_ID
    state = evaluate_as_maker_tick(make_mock_pairs(), sol_usd=84.50, client_state=state)
    assert len(state["maker_slots"]) == 6
    assert abs(state["total_sol_vault"] - 0.96000) < 1e-6
    assert state["total_token_val_sol"] == 0.0
    print(f"  [OK] 6 Maker Vaults Initialized | Total Pure SOL in Vaults: {state['total_sol_vault']:.5f} SOL | Tokens Held: 0.0")

    print("\n=== TEST 2: Stationary Market (10 Ticks With Zero Price Change -> ZERO Fake Fills) ===")
    for _ in range(10):
        state = evaluate_as_maker_tick(make_mock_pairs(), sol_usd=84.50, client_state=state)
    assert state["total_maker_fills"] == 0, "Stationary prices must NEVER trigger fake fills!"
    print("  [OK] 10 stationary ticks -> 0 Fills (100% Real Price-Action Enforcement!)")

    print("\n=== TEST 3: Crash Shield (Sharp -2.5% Dump -> Buy Paused, Zero Falling Knife) ===")
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.975}), sol_usd=84.50, client_state=state)
    jup_slot = state["maker_slots"]["JUP"]
    assert jup_slot["tokens_held"] == 0.0, "Crash Shield must prevent buying during a sharp -2.5% crash tick!"
    assert jup_slot["toxic_shield_active"] is True
    print(f"  [OK] JUP Dumped -2.5% | Shield Active: {jup_slot['toxic_shield_active']} | JUP Bought: 0.0")

    print("\n=== TEST 4: Real Gentle Dip (-0.18%) Touching Buy Target -> Real Maker Bid Fill ===")
    # RAY dips gently by -0.18% (crossing the -0.12% Buy Target without triggering the -0.45% Crash Shield)
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.975, "RAY": 0.9982}), sol_usd=84.50, client_state=state)
    assert state["total_bid_fills"] == 1, "Expected RAY real -0.18% dip to fill Maker Bid!"
    ray_slot = state["maker_slots"]["RAY"]
    assert ray_slot["tokens_held"] > 0
    print(f"  [OK] RAY Bought on Real -0.18% Dip: {ray_slot['tokens_held']:.4f} RAY | Maker Fee Earned: +{ray_slot['maker_rebates_earned_sol']:.6f} SOL")

    print("\n=== TEST 5: Real Bounce (+0.30%) Crossing Sell Target -> 100% Sold Back to SOL ===")
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.975, "RAY": 1.0015}), sol_usd=84.50, client_state=state)
    assert state["total_ask_fills"] == 1, "Expected RAY bounce to cross Sell Target and evacuate 100% to SOL!"
    ray_slot = state["maker_slots"]["RAY"]
    assert ray_slot["tokens_held"] == 0.0
    assert ray_slot["sol_cash"] > 0.16000
    print(f"  [OK] RAY Vault Back in 100% SOL: {ray_slot['sol_cash']:.5f} SOL (Started 0.16000 SOL)")
    print(f"  [OK] Net Pure SOL Profit Locked: +{state['accumulated_sol_profit']:.5f} SOL | Maker Fees Earned: +{state['total_maker_rebates_sol']:.5f} SOL")
    print("\nALL 5 REAL-EXECUTION SMART MAKER TESTS PASSED 100%!")


if __name__ == "__main__":
    run_tests()
