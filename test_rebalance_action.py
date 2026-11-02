from backend.demo_engine import get_initial_state, evaluate_demo_tick

state = get_initial_state()
state['is_running'] = True

# Step 1: Open slot on KMNO (0.50 SOL tranche: 0.25 Cash + 0.25 KMNO)
mock1 = [{'base_token': 'KMNO', 'current_ratio': 0.00034, 'z_score': -2.5, 'target_yield_pct': 3.5}]
state = evaluate_demo_tick(mock1, 95.0, client_state=state)
slot = state['active_slots']['KMNO']
print(f"1. Slot Initialized: Cash = {slot['slot_cash']:.4f} SOL | Tokens = {slot['tokens_held']:.1f} KMNO | Drift = {slot['drift_pct']}%")

# Step 2: KMNO drops by 12% in price -> triggers Rebalance Buy (DCA)
mock2 = [{'base_token': 'KMNO', 'current_ratio': 0.00034 * 0.88, 'z_score': -3.2, 'target_yield_pct': 3.5}]
state = evaluate_demo_tick(mock2, 95.0, client_state=state)
slot2 = state['active_slots']['KMNO']
print(f"2. After 12% Price Drop: Cash = {slot2['slot_cash']:.4f} SOL | Tokens = {slot2['tokens_held']:.1f} KMNO | Cycles = {slot2['cycles_completed']}")
print(f"   Latest Action: {state['trade_history'][0]['action']}")
print(f"   Reason: {state['trade_history'][0]['reason']}")
print(f"   Harvested Alpha: +{slot2['harvested_alpha_sol']:.5f} SOL")

# Step 3: KMNO pumps back up by 15% -> triggers Rebalance Sell (Take Profit into Cash)
mock3 = [{'base_token': 'KMNO', 'current_ratio': 0.00034 * 1.05, 'z_score': -1.0, 'target_yield_pct': 2.5}]
state = evaluate_demo_tick(mock3, 95.0, client_state=state)
slot3 = state['active_slots']['KMNO']
print(f"3. After 15% Price Pump: Cash = {slot3['slot_cash']:.4f} SOL | Tokens = {slot3['tokens_held']:.1f} KMNO | Cycles = {slot3['cycles_completed']}")
print(f"   Latest Action: {state['trade_history'][0]['action']}")
print(f"   Reason: {state['trade_history'][0]['reason']}")
print(f"   Total Harvested Alpha: +{state['total_harvested_alpha_sol']:.5f} SOL")
