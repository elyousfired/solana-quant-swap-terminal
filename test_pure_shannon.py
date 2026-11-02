from backend.demo_engine import get_initial_state, evaluate_demo_tick

# Test scenario reflecting the user's real situation:
# PUMP is overbought/high at Z = +1.94 (yield 0.0%)
# KMNO is in an oversold dip at Z = -2.5 (yield 3.5%)
# RAY is in an oversold dip at Z = -1.9 (yield 3.1%)
# JTO is in a dip at Z = -1.7 (yield 2.5%)
# JUP is in a dip at Z = -1.5 (yield 2.2%)
# MET is neutral at Z = 0.5 (yield 1.0%)
mock_pairs = [
    {'base_token': 'KMNO', 'current_ratio': 0.00034, 'z_score': -2.5, 'target_yield_pct': 3.5},
    {'base_token': 'PUMP', 'current_ratio': 0.000042, 'z_score': 1.94, 'target_yield_pct': 0.0},
    {'base_token': 'RAY', 'current_ratio': 0.017, 'z_score': -1.9, 'target_yield_pct': 3.1},
    {'base_token': 'JTO', 'current_ratio': 0.0039, 'z_score': -1.7, 'target_yield_pct': 2.5},
    {'base_token': 'JUP', 'current_ratio': 0.0027, 'z_score': -1.5, 'target_yield_pct': 2.2},
    {'base_token': 'MET', 'current_ratio': 0.0029, 'z_score': 0.5, 'target_yield_pct': 1.0}
]

state = get_initial_state()
state['is_running'] = True

print("=== Test 1: PUMP at Z=+1.94 MUST NOT ENTER (Waiting Dip Filter) ===")
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("Active Slots Opened:", list(state["active_slots"].keys()))
pump_status = [s for s in state["scanned_pairs_status"] if s["symbol"] == "PUMP"][0]
print(f"PUMP Status: {pump_status['status_text']} | Gate Status: {pump_status['gate_status']}")
assert "PUMP" not in state["active_slots"], "CRITICAL ERROR: PUMP entered despite Z > -1.4!"
assert "KMNO" in state["active_slots"], "KMNO should have entered as it is in a qualified dip!"
print("PASSED: PUMP was filtered out and KMNO entered cleanly!\n")

print("=== Test 2: Multi-Slot Expansion without 3-Slot Limit ===")
# Tick 2: RAY should enter (Slot 2)
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print(f"Tick 2 Slots: {list(state['active_slots'].keys())} | Central Cash: {state['central_cash_sol']:.4f} SOL")

# Tick 3: JTO should enter (Slot 3)
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print(f"Tick 3 Slots: {list(state['active_slots'].keys())} | Central Cash: {state['central_cash_sol']:.4f} SOL")

# Tick 4: JUP should enter (Slot 4 - previously capped at 3!)
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print(f"Tick 4 Slots: {list(state['active_slots'].keys())} | Central Cash: {state['central_cash_sol']:.4f} SOL")
assert len(state["active_slots"]) == 4, f"Expected 4 active slots, found {len(state['active_slots'])}"
print("PASSED: Multi-slot expansion beyond 3 slots verified successfully!\n")

print("=== Test 3: Natural Fee Gate Stop when Cash < 0.020 SOL ===")
# Set cash low so prospective tranche < 0.020 SOL
state["central_cash_sol"] = 0.015  # Tranche would be 0.0075 SOL < 0.020 SOL
state["active_slots"].clear()
# Add another dip token
mock_pairs.append({'base_token': 'NEWDIP', 'current_ratio': 0.001, 'z_score': -2.0, 'target_yield_pct': 3.0})
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print(f"Central Cash: {state['central_cash_sol']} SOL | Slots opened: {len(state['active_slots'])}")
assert len(state["active_slots"]) == 0, "Fee gate should have blocked trade on insufficient cash!"
print("PASSED: Pre-Flight Fee Gate successfully protected wallet from fee destruction!\n")

print("=== ALL TESTS PASSED WITH 100% SUCCESS! ===")
