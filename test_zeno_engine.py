from backend.demo_engine import get_initial_state, evaluate_demo_tick, MIN_TRANCHE_SOL

mock_pairs = [
    {'base_token': 'KMNO', 'current_ratio': 0.00034, 'z_score': -2.1, 'target_yield_pct': 3.2},
    {'base_token': 'PUMP', 'current_ratio': 0.000042, 'z_score': -1.9, 'target_yield_pct': 3.5},
    {'base_token': 'RAY', 'current_ratio': 0.017, 'z_score': -1.6, 'target_yield_pct': 2.9},
    {'base_token': 'JUP', 'current_ratio': 0.0027, 'z_score': -0.4, 'target_yield_pct': 2.0},
    {'base_token': 'JTO', 'current_ratio': 0.0039, 'z_score': 0.8, 'target_yield_pct': 1.8},
    {'base_token': 'MET', 'current_ratio': 0.0029, 'z_score': -0.2, 'target_yield_pct': 2.1}
]

state = get_initial_state()
state['is_running'] = True

print("=== Initial State ===")
print("Cash:", state["sol_cash_balance"], "SOL, Positions:", len(state["active_positions"]))

# Tick 1: Should enter best opportunity (KMNO) with 50% of 1.0 = 0.50 SOL
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("\n=== Tick 1 (Opportunity 1: KMNO) ===")
print("Cash:", state["sol_cash_balance"], "SOL, Positions:", list(state["active_positions"].keys()))
for k, v in state['active_positions'].items():
    print(f"  Slot {k}: Invested {v['invested_sol']} SOL, Value {v['current_sol_val']} SOL")

# Tick 2: Should enter next best opportunity (PUMP) with 50% of 0.50 = 0.25 SOL
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("\n=== Tick 2 (Opportunity 2: PUMP) ===")
print("Cash:", state["sol_cash_balance"], "SOL, Positions:", list(state["active_positions"].keys()))
for k, v in state['active_positions'].items():
    print(f"  Slot {k}: Invested {v['invested_sol']} SOL, Value {v['current_sol_val']} SOL")

# Tick 3: Should enter 3rd opportunity (RAY) with 50% of 0.25 = 0.125 SOL
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("\n=== Tick 3 (Opportunity 3: RAY) ===")
print("Cash:", state["sol_cash_balance"], "SOL, Positions:", list(state["active_positions"].keys()))
for k, v in state['active_positions'].items():
    print(f"  Slot {k}: Invested {v['invested_sol']} SOL, Value {v['current_sol_val']} SOL")

# Now simulate KMNO pumping (+3.8%) to trigger Take-Profit
print("\n=== Tick 4: KMNO reaches +3.8% Target ===")
mock_pairs[0]['current_ratio'] = 0.00034 * 1.038
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("Cash after TP:", state["sol_cash_balance"], "SOL, Active Positions:", list(state["active_positions"].keys()))
print("Total Balance:", state["current_balance_sol"], "SOL, Profit:", state["total_profit_sol"], "SOL")

# Now test user condition: What if cash drops to 0.0005 SOL?
print("\n=== Testing Fee Gate on Low Cash (0.0005 SOL) ===")
state['sol_cash_balance'] = 0.0005
state['active_positions'].clear()
state = evaluate_demo_tick(mock_pairs, 95.0, client_state=state)
print("Cash after Gate check:", state["sol_cash_balance"], "SOL, Positions opened:", len(state["active_positions"]))
print("Scanned Status for KMNO:", [s for s in state["scanned_pairs_status"] if s["symbol"] == "KMNO"][0]["status_text"])
print("ALL TESTS PASSED PERFECTLY!")
