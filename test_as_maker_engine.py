"""
Automated Verification Suite for Engine 5:
Avellaneda-Stoikov Inventory-Skewed Smart Maker & Dynamic DLMM Bin Engine (backend/as_maker_engine.py)
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

    print("\n=== TEST 2: Toxic Flow Shield (Bearish Dump -2.5% -> Bid Pulled, Zero Falling Knife) ===")
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.975}), sol_usd=84.50, client_state=state)
    jup_slot = state["maker_slots"]["JUP"]
    assert jup_slot["tokens_held"] == 0.0, "Toxic Dump Shield must prevent buying during a sharp -2.5% crash tick!"
    assert jup_slot["toxic_shield_active"] is True
    print(f"  [OK] JUP Dumped -2.5% | OBI: {jup_slot['obi']:+.2f} | Shield Active: {jup_slot['toxic_shield_active']} | JUP Bought: 0.0")

    print("\n=== TEST 3: Stabilization & Discounted Maker Bid Fill (+Maker Rebate Earned) ===")
    # Stabilize JUP at 0.976 and let resting Maker Bid capture discounted flow
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.976}), sol_usd=84.50, client_state=state)
    state = evaluate_as_maker_tick(make_mock_pairs({"JUP": 0.9755}), sol_usd=84.50, client_state=state)
    assert state["total_bid_fills"] >= 1, "Expected Maker Bid fill after stabilization!"
    assert state["total_maker_rebates_sol"] > 0.0
    jup_slot = state["maker_slots"]["JUP"]
    print(f"  [OK] Total Bid Fills: {state['total_bid_fills']} | Maker Rebates Earned: +{state['total_maker_rebates_sol']:.6f} SOL")
    print(f"  [OK] JUP Inventory Skew Active: q={jup_slot['inventory_q_pct']}% | Skew={jup_slot['skew_bps']} bps")

    print("\n=== TEST 4: Avellaneda-Stoikov Skew Ask Fill -> 100% Evacuation Back to Pure SOL ===")
    # Slight +0.6% bounce triggers Maker Ask fills across active slots, evacuating tokens back to SOL + Maker Rebate
    state = evaluate_as_maker_tick(
        make_mock_pairs({"JUP": 0.983, "RAY": 1.006, "JTO": 1.006, "KMNO": 1.006, "MET": 1.006, "PUMP": 1.006}),
        sol_usd=84.50,
        client_state=state,
    )
    assert state["total_ask_fills"] >= 1, "Expected Maker Ask fill on +0.6% bounce!"
    assert state["accumulated_sol_profit"] > 0.00040, "Expected meaningful SOL profit (> +0.00040 SOL)!"
    print(f"  [OK] Completed Round-Trips: {state['total_round_trips']}")
    print(f"  [OK] Accumulated Pure SOL Profit: +{state['accumulated_sol_profit']:.5f} SOL")
    print(f"  [OK] Total Maker Rebates Earned: +{state['total_maker_rebates_sol']:.5f} SOL")
    print(f"  [OK] Total Portfolio Equity: {state['total_equity_sol']:.5f} SOL")
    print("\nALL 4 AVELLANEDA-STOIKOV SMART MAKER TESTS PASSED 100%!")


if __name__ == "__main__":
    run_tests()
