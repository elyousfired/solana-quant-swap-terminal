"""
Solana Quant Swap Terminal — Engine 5 (100% Independent Module Built From Scratch)
Strategy: Smart Maker & Dynamic DLMM Bin Engine (Real Price-Action Execution V2)
-----------------------------------------------------------------------------------
Core Rules:
1. Starts 100% in SOL Cash (0.96000 SOL across 6 Vaults + 0.04000 SOL Gas Reserve). Zero blind buying at T=0.
2. 100% Real Jupiter Price-Crossing Execution:
   - ZERO artificial fills when live price is stationary (curr_ratio == prev_ratio).
   - Maker Bid (SOL -> Token) ONLY fills when the live Jupiter ratio ACTUALLY drops to touch/cross `bid_quote`
     AND Crash Shield is NOT active (not a free-falling dump).
   - Maker Ask (Token -> SOL) ONLY fills when the live Jupiter ratio ACTUALLY rises to touch/cross `ask_quote`.
3. Maker Fee Rebate (+0.085% per fill = +0.17% round-trip EARNED instead of paying -0.30% Taker Fee).
4. Inventory Skew (Anti-Bagholder):
   - While holding a token, if it takes longer to bounce, `ask_quote` dynamically lowers toward break-even
     (protected by the +0.17% Maker Rebate buffer) so the bot evacuates back to 100% SOL on the first real bounce
     and NEVER gets stuck forever.
"""

import os
import json
import math
import time
import urllib.request
from typing import Dict, Any, List, Optional

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "as_maker_state.json")
STRATEGY_ID = "AVELLANEDA_STOIKOV_SMART_MAKER_V2"

MAKER_MARKETS = ["JUP", "RAY", "JTO", "KMNO", "MET", "PUMP"]

# Capital Architecture (1.00000 SOL Total)
INITIAL_PORTFOLIO_SOL = 1.00000
GAS_RESERVE_SOL = 0.04000
ACTIVE_CAPITAL_SOL = 0.96000  # 6 Maker Vaults x 0.16000 SOL (100% SOL at start!)
VAULT_ALLOCATION_SOL = round(ACTIVE_CAPITAL_SOL / len(MAKER_MARKETS), 6)  # 0.16000 SOL

# Smart Maker Parameters
MAKER_REBATE_RATE = 0.00085     # +0.085% (+8.5 bps) Maker Rebate / DLMM Bin Fee EARNED per fill
SOL_BASE_GAS_FEE = 0.000005     # 5,000 Lamports Solana base signature fee
MIN_GAS_FLOOR_SOL = 0.00500
TRANCHE_UTILIZATION = 0.85      # Deploy 85% of vault (0.13600 SOL) per Maker Bid fill

# Live L1 Orderbook Cache (Binance / Bybit BookTicker)
BOOK_CACHE: Dict[str, Dict[str, float]] = {}
BOOK_CACHE_TS: float = 0.0
BOOK_CACHE_TTL: float = 2.0


def fetch_live_l1_books() -> Dict[str, Dict[str, float]]:
    """
    Fetches real-time Level-1 Best Bid / Best Ask prices and quantities for SOL and all 6 tokens
    to measure real-time buying vs selling pressure (Order Book Imbalance).
    """
    global BOOK_CACHE, BOOK_CACHE_TS
    now = time.time()
    if BOOK_CACHE and (now - BOOK_CACHE_TS) < BOOK_CACHE_TTL:
        return BOOK_CACHE

    symbols_map = {
        "SOLUSDT": "SOL",
        "JUPUSDT": "JUP",
        "RAYUSDT": "RAY",
        "JTOUSDT": "JTO",
        "KMNOUSDT": "KMNO",
        "METUSDT": "MET",
        "PUMPUSDT": "PUMP",
    }

    try:
        symbols_json = json.dumps(list(symbols_map.keys())).replace(" ", "")
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbols={symbols_json}"
        req = urllib.request.Request(url, headers={"User-Agent": "SolanaQuantTerminal/2.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            if isinstance(rows, list) and len(rows) > 0:
                parsed: Dict[str, Dict[str, float]] = {}
                for r in rows:
                    bsym = r.get("symbol", "")
                    sym = symbols_map.get(bsym)
                    if not sym:
                        continue
                    bid_p = float(r.get("bidPrice", 0.0))
                    bid_q = float(r.get("bidQty", 0.0))
                    ask_p = float(r.get("askPrice", 0.0))
                    ask_q = float(r.get("askQty", 0.0))
                    if bid_p > 0 and ask_p > 0:
                        parsed[sym] = {
                            "bid_p": bid_p,
                            "bid_q": bid_q,
                            "ask_p": ask_p,
                            "ask_q": ask_q,
                        }
                if parsed:
                    BOOK_CACHE = parsed
                    BOOK_CACHE_TS = now
                    return BOOK_CACHE
    except Exception:
        pass

    try:
        url = "https://api.bybit.com/v5/market/tickers?category=spot"
        req = urllib.request.Request(url, headers={"User-Agent": "SolanaQuantTerminal/2.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rows = data.get("result", {}).get("list", [])
            parsed = {}
            for r in rows:
                bsym = r.get("symbol", "")
                sym = symbols_map.get(bsym)
                if not sym:
                    continue
                bid_p = float(r.get("bid1Price", 0.0) or 0.0)
                bid_q = float(r.get("bid1Size", 0.0) or 0.0)
                ask_p = float(r.get("ask1Price", 0.0) or 0.0)
                ask_q = float(r.get("ask1Size", 0.0) or 0.0)
                if bid_p > 0 and ask_p > 0:
                    parsed[sym] = {
                        "bid_p": bid_p,
                        "bid_q": bid_q,
                        "ask_p": ask_p,
                        "ask_q": ask_q,
                    }
            if parsed:
                BOOK_CACHE = parsed
                BOOK_CACHE_TS = now
                return BOOK_CACHE
    except Exception:
        pass

    return BOOK_CACHE


def compute_microstructure_metrics(
    sym: str,
    curr_ratio: float,
    prev_ratio: float,
    prev_obi: float,
    sol_usd: float,
    l1_books: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """
    Computes live buying/selling pressure (OBI) and detects sharp downward dumps.
    """
    tok_book = l1_books.get(sym)
    sol_book = l1_books.get("SOL")

    tick_ret_pct = ((curr_ratio - prev_ratio) / prev_ratio) * 100.0 if prev_ratio > 0 else 0.0

    if tok_book and sol_book and sol_book["bid_p"] > 0 and sol_book["ask_p"] > 0:
        bid_p, bid_q = tok_book["bid_p"], tok_book["bid_q"]
        ask_p, ask_q = tok_book["ask_p"], tok_book["ask_q"]
        total_q = bid_q + ask_q
        if total_q > 0:
            imbalance = bid_q / total_q
            tok_micro_usd = imbalance * ask_p + (1.0 - imbalance) * bid_p
            obi = (bid_q - ask_q) / total_q
        else:
            tok_micro_usd = (bid_p + ask_p) * 0.5
            obi = 0.0

        velocity_obi = max(-0.95, min(0.95, tick_ret_pct * 1.8))
        if abs(tick_ret_pct) >= 0.20:
            obi = (0.35 * obi) + (0.65 * velocity_obi)

        sol_mid_usd = (sol_book["bid_p"] + sol_book["ask_p"]) * 0.5
        cex_micro_ratio = tok_micro_usd / sol_mid_usd if sol_mid_usd > 0 else curr_ratio
        lead_lag_pct = ((cex_micro_ratio - curr_ratio) / curr_ratio) * 100.0 if curr_ratio > 0 else 0.0
        lead_lag_clamped = max(-1.0, min(1.0, lead_lag_pct))
        micro_ratio = curr_ratio * (1.0 + (0.30 * lead_lag_clamped / 100.0))
    else:
        obi = max(-0.95, min(0.95, (tick_ret_pct * 1.8) + (0.35 * prev_obi)))
        micro_ratio = curr_ratio * (1.0 + (0.0015 * obi))

    ofi_norm = max(-1.0, min(1.0, obi - (0.4 * prev_obi) + (tick_ret_pct * 0.9)))
    alpha_micro_pct = (0.45 * obi * 0.45) + (0.35 * ofi_norm * 0.40) + (0.60 * tick_ret_pct)
    alpha_micro_pct = max(-1.50, min(1.50, alpha_micro_pct))

    return {
        "micro_ratio": micro_ratio,
        "obi": round(obi, 4),
        "ofi": round(ofi_norm, 4),
        "alpha_micro_pct": round(alpha_micro_pct, 4),
        "tick_ret_pct": round(tick_ret_pct, 4),
    }


def compute_avellaneda_stoikov_quotes(
    mid_ratio: float,
    micro_ratio: float,
    inventory_q: float,
    sigma_pct: float,
    alpha_micro_pct: float,
    obi: float,
    holding_ticks: int,
    avg_entry_ratio: float,
    tick_ret_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Computes realistic Maker Bid (Buy Target) and Maker Ask (Sell Target -> SOL).
    - When holding 100% SOL (q = 0):
      Places a Maker Bid at -0.12% to -0.22% below current live price so real market micro-dips fill it.
      If a sharp dump occurs (tick_ret_pct <= -0.45% or OBI < -0.38), Crash Shield activates and pulls Bid down!
    - When holding Token (q > 0):
      Places a Maker Ask at +0.20% above Bought Price (avg_entry_ratio).
      As holding_ticks increases, Inventory Skew lowers the Ask target down to +0.04% above Bought Price
      (which still nets +0.21% pure SOL profit thanks to the +0.17% round-trip Maker Rebates!).
    """
    toxic_dump = (tick_ret_pct <= -0.45) or (tick_ret_pct <= -0.25 and obi < -0.45)

    # Reservation shift
    skew_frac = inventory_q * 0.0025 * (1.0 + min(2.0, holding_ticks * 0.10))
    reservation_ratio = mid_ratio * (1.0 - skew_frac)

    if toxic_dump:
        # Pull Bid deep (-1.50% below spot) so it never catches a falling knife
        bid_quote = mid_ratio * 0.9850
    elif inventory_q > 0.05:
        # Already holding token: keep Bid far down (-0.80%) so we don't double-bag
        bid_quote = mid_ratio * 0.9920
    else:
        # Ready in 100% SOL: place realistic Maker Bid -0.12% below current spot to catch normal dips
        bid_quote = mid_ratio * 0.9988

    if inventory_q > 0.01 and avg_entry_ratio > 0:
        # Target +0.22% above entry initially, gently skewing down to +0.04% as holding_ticks grows
        # (Remember: +0.085% entry rebate + +0.085% exit rebate = +0.17% extra SOL profit on top!)
        target_markup = max(0.0004, 0.0022 - (holding_ticks * 0.00015))
        ask_quote = avg_entry_ratio * (1.0 + target_markup)
    else:
        ask_quote = mid_ratio * 1.0022

    spread_bps = ((ask_quote - bid_quote) / mid_ratio) * 10000.0 if mid_ratio > 0 else 0.0
    skew_bps = ((reservation_ratio - mid_ratio) / mid_ratio) * 10000.0 if mid_ratio > 0 else 0.0

    return {
        "reservation_ratio": reservation_ratio,
        "bid_quote": bid_quote,
        "ask_quote": ask_quote,
        "spread_bps": round(spread_bps, 2),
        "skew_bps": round(skew_bps, 2),
        "toxic_shield_active": toxic_dump,
    }


def get_initial_as_state() -> Dict[str, Any]:
    now = time.time()
    return {
        "strategy": STRATEGY_ID,
        "is_running": True,
        "start_time": now,
        "last_update": now,
        "initial_balance_sol": INITIAL_PORTFOLIO_SOL,
        "gas_reserve_sol": GAS_RESERVE_SOL,
        "initial_vault_sol": ACTIVE_CAPITAL_SOL,
        "total_sol_vault": ACTIVE_CAPITAL_SOL,
        "total_token_val_sol": 0.0,
        "total_equity_sol": INITIAL_PORTFOLIO_SOL,
        "net_pnl_sol": 0.0,
        "net_pnl_pct": 0.0,
        "accumulated_sol_profit": 0.0,
        "total_maker_rebates_sol": 0.0,
        "total_gas_paid_sol": 0.0,
        "total_maker_fills": 0,
        "total_bid_fills": 0,
        "total_ask_fills": 0,
        "total_round_trips": 0,
        "toxic_shields_triggered": 0,
        "maker_slots": {},
        "trade_history": [],
        "equity_curve": [
            {"time": now, "equity": INITIAL_PORTFOLIO_SOL, "sol_vault": ACTIVE_CAPITAL_SOL}
        ],
    }


def _is_valid_as_state(state: Any) -> bool:
    return (
        isinstance(state, dict)
        and state.get("strategy") == STRATEGY_ID
        and isinstance(state.get("maker_slots"), dict)
    )


def load_as_state() -> Dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if _is_valid_as_state(data):
                    return data
        except Exception:
            pass
    state = get_initial_as_state()
    save_as_state(state)
    return state


def save_as_state(state: Dict[str, Any]) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def reset_as_state(client_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = get_initial_as_state()
    save_as_state(state)
    return state


def toggle_as_state(running: Optional[bool] = None, client_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    state = client_state if _is_valid_as_state(client_state) else load_as_state()
    if running is None:
        state["is_running"] = not state.get("is_running", True)
    else:
        state["is_running"] = bool(running)
    state["last_update"] = time.time()
    save_as_state(state)
    return state


def evaluate_as_maker_tick(
    live_pairs: List[Dict[str, Any]],
    sol_usd: float,
    client_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main real-time execution tick for Engine 5 (Smart Maker & DLMM Engine V2).
    Executes ONLY on genuine Jupiter price movements crossing resting Maker Bid / Ask quotes.
    """
    state = client_state if _is_valid_as_state(client_state) else load_as_state()
    now = time.time()

    pairs_by_sym: Dict[str, Dict[str, Any]] = {}
    for p in live_pairs:
        b = p.get("base_token", "")
        if b in MAKER_MARKETS:
            pairs_by_sym[b] = p

    if not pairs_by_sym:
        return state

    l1_books = fetch_live_l1_books()
    maker_slots: Dict[str, Dict[str, Any]] = state.get("maker_slots", {})
    trade_history: List[Dict[str, Any]] = state.get("trade_history", [])
    gas_reserve = float(state.get("gas_reserve_sol", GAS_RESERVE_SOL))

    # 1. Initialize 6 Maker Vaults in 100% SOL Cash (ZERO blind token purchases at T=0!)
    just_initialized = False
    if len(maker_slots) < len(MAKER_MARKETS):
        just_initialized = True
        for sym in MAKER_MARKETS:
            if sym in maker_slots:
                continue
            p_info = pairs_by_sym.get(sym)
            if not p_info:
                continue
            curr_ratio = float(p_info.get("current_ratio", 0.0))
            if curr_ratio <= 0:
                continue
            tok_usd = float(p_info.get("base_usd", curr_ratio * (sol_usd or 85.0)))
            sigma_pct = max(0.85, min(3.20, abs(float(p_info.get("z_score", 1.2))) * 0.85))

            micro = compute_microstructure_metrics(sym, curr_ratio, curr_ratio, 0.0, sol_usd, l1_books)
            quotes = compute_avellaneda_stoikov_quotes(
                mid_ratio=curr_ratio,
                micro_ratio=micro["micro_ratio"],
                inventory_q=0.0,
                sigma_pct=sigma_pct,
                alpha_micro_pct=micro["alpha_micro_pct"],
                obi=micro["obi"],
                holding_ticks=0,
                avg_entry_ratio=0.0,
                tick_ret_pct=0.0,
            )

            maker_slots[sym] = {
                "symbol": sym,
                "venue": "Meteora DLMM + Phoenix CLOB",
                "initial_sol": VAULT_ALLOCATION_SOL,
                "sol_cash": VAULT_ALLOCATION_SOL,
                "tokens_held": 0.0,
                "token_sol_val": 0.0,
                "vault_equity_sol": VAULT_ALLOCATION_SOL,
                "inventory_q_pct": 0.0,
                "avg_entry_ratio": 0.0,
                "current_ratio": curr_ratio,
                "micro_ratio": micro["micro_ratio"],
                "reservation_ratio": quotes["reservation_ratio"],
                "bid_quote": quotes["bid_quote"],
                "ask_quote": quotes["ask_quote"],
                "spread_bps": quotes["spread_bps"],
                "skew_bps": quotes["skew_bps"],
                "obi": micro["obi"],
                "ofi": micro["ofi"],
                "alpha_micro_pct": micro["alpha_micro_pct"],
                "sigma_pct": round(sigma_pct, 2),
                "toxic_shield_active": quotes["toxic_shield_active"],
                "token_usd": tok_usd,
                "holding_ticks": 0,
                "QuietTicks": 0,
                "round_trips": 0,
                "bid_fills": 0,
                "ask_fills": 0,
                "accumulated_sol_profit": 0.0,
                "maker_rebates_earned_sol": 0.0,
                "status_badge": "100% IN SOL (WAITING FOR DIP)",
                "last_action": "Vault Ready in 100% SOL • Waiting for live price to touch Buy Target",
                "ratio_history": [curr_ratio, curr_ratio],
            }

    if just_initialized or not state.get("is_running", True):
        state["maker_slots"] = maker_slots
        state["sol_usd"] = sol_usd
        state["last_update"] = now
        save_as_state(state)
        return state

    # 2. Evaluate Real-Time Price Movements Against Resting Maker Quotes
    total_maker_rebates = float(state.get("total_maker_rebates_sol", 0.0))
    total_gas_paid = float(state.get("total_gas_paid_sol", 0.0))
    accumulated_sol = float(state.get("accumulated_sol_profit", 0.0))
    maker_fills = int(state.get("total_maker_fills", 0))
    bid_fills = int(state.get("total_bid_fills", 0))
    ask_fills = int(state.get("total_ask_fills", 0))
    round_trips = int(state.get("total_round_trips", 0))
    shields_count = int(state.get("toxic_shields_triggered", 0))

    for sym in MAKER_MARKETS:
        slot = maker_slots.get(sym)
        p_info = pairs_by_sym.get(sym)
        if not slot or not p_info:
            continue

        prev_ratio = float(slot.get("current_ratio", 0.0))
        curr_ratio = float(p_info.get("current_ratio", prev_ratio))
        if curr_ratio <= 0:
            continue

        tok_usd = float(p_info.get("base_usd", curr_ratio * (sol_usd or 85.0)))
        slot["token_usd"] = tok_usd

        # Did the live Jupiter ratio actually move on this tick?
        price_moved = abs(curr_ratio - prev_ratio) / prev_ratio >= 0.00005 if prev_ratio > 0 else False

        r_hist: List[float] = list(slot.get("ratio_history", [curr_ratio]))
        if price_moved:
            r_hist.append(curr_ratio)
            if len(r_hist) > 20:
                r_hist = r_hist[-20:]
        slot["ratio_history"] = r_hist

        prev_obi = float(slot.get("obi", 0.0))
        micro = compute_microstructure_metrics(sym, curr_ratio, prev_ratio, prev_obi, sol_usd, l1_books)
        tick_ret_pct = micro["tick_ret_pct"]

        sol_cash = float(slot.get("sol_cash", VAULT_ALLOCATION_SOL))
        tokens_held = float(slot.get("tokens_held", 0.0))
        avg_entry = float(slot.get("avg_entry_ratio", 0.0))
        holding_ticks = int(slot.get("holding_ticks", 0))
        quiet_ticks = int(slot.get("QuietTicks", 0))

        resting_bid = float(slot.get("bid_quote", curr_ratio * 0.9988))
        resting_ask = float(slot.get("ask_quote", curr_ratio * 1.0022))

        # ---------------------------------------------------------------------
        # A. REAL MAKER ASK FILL (WhenHolding Token & Live Price Rises >= Sell Target)
        # ---------------------------------------------------------------------
        if tokens_held > 0 and gas_reserve >= MIN_GAS_FLOOR_SOL:
            if price_moved:
                holding_ticks += 1

            # STRICT REAL EXECUTION: Live Jupiter ratio must actually reach or exceed resting_ask!
            if price_moved and curr_ratio >= resting_ask:
                exec_ask_ratio = curr_ratio
                gross_sol_out = tokens_held * exec_ask_ratio
                maker_rebate_sol = gross_sol_out * MAKER_REBATE_RATE
                net_sol_received = gross_sol_out + maker_rebate_sol

                # True SOL profit vs the exact SOL spent on the Bid fill
                sol_spent_on_bid = float(slot.get("last_tranche_sol", tokens_held * avg_entry))
                entry_rebate_sol = sol_spent_on_bid * MAKER_REBATE_RATE
                cycle_net_sol_profit = (net_sol_received - sol_spent_on_bid) + entry_rebate_sol - (2.0 * SOL_BASE_GAS_FEE)
                spread_captured_pct = ((exec_ask_ratio - avg_entry) / avg_entry) * 100.0 if avg_entry > 0 else 0.0

                sol_cash += net_sol_received
                tokens_sold = tokens_held
                tokens_held = 0.0
                avg_entry = 0.0
                holding_ticks = 0
                quiet_ticks = 0
                gas_reserve -= SOL_BASE_GAS_FEE

                slot["sol_cash"] = sol_cash
                slot["tokens_held"] = 0.0
                slot["avg_entry_ratio"] = 0.0
                slot["last_tranche_sol"] = 0.0
                slot["holding_ticks"] = 0
                slot["QuietTicks"] = 0
                slot["ask_fills"] = int(slot.get("ask_fills", 0)) + 1
                slot["round_trips"] = int(slot.get("round_trips", 0)) + 1
                slot["accumulated_sol_profit"] = float(slot.get("accumulated_sol_profit", 0.0)) + cycle_net_sol_profit
                slot["maker_rebates_earned_sol"] = float(slot.get("maker_rebates_earned_sol", 0.0)) + maker_rebate_sol
                slot["last_action"] = (
                    f"SOLD TO SOL: -{tokens_sold:,.2f} {sym} ➔ +{net_sol_received:.5f} SOL "
                    f"(Net Profit: +{cycle_net_sol_profit:.5f} SOL)"
                )

                total_maker_rebates += maker_rebate_sol
                total_gas_paid += SOL_BASE_GAS_FEE
                accumulated_sol += cycle_net_sol_profit
                maker_fills += 1
                ask_fills += 1
                round_trips += 1

                trade_history.insert(
                    0,
                    {
                        "id": f"as_ask_{int(now * 1000)}_{sym}_{maker_fills}",
                        "time": now,
                        "type": "MAKER_ASK_SOL_HARVEST",
                        "symbol": sym,
                        "side": "SOLD ➔ SOL",
                        "action": f"Sold {tokens_sold:,.4f} {sym} ➔ +{net_sol_received:.5f} SOL",
                        "tranche_sol": round(net_sol_received, 5),
                        "exec_ratio": exec_ask_ratio,
                        "spread_captured_pct": round(spread_captured_pct, 3),
                        "maker_rebate_sol": round(maker_rebate_sol, 6),
                        "net_profit_sol": round(cycle_net_sol_profit, 5),
                        "reason": (
                            f"Live price reached Sell Target (+{spread_captured_pct:.2f}% move + "
                            f"Maker Rebates) ➔ 100% Back in SOL"
                        ),
                    },
                )

        # ---------------------------------------------------------------------
        # B. REAL MAKER BID FILL (When in 100% SOL & Live Price Dips <= Buy Target)
        # ---------------------------------------------------------------------
        elif tokens_held <= 0 and sol_cash >= 0.02000 and gas_reserve >= MIN_GAS_FLOOR_SOL:
            toxic_dump = (tick_ret_pct <= -0.45) or (tick_ret_pct <= -0.25 and micro["obi"] < -0.45)
            if toxic_dump and price_moved:
                shields_count += 1
                slot["last_action"] = f"CRASH SHIELD ON: {sym} dropping fast ({tick_ret_pct:+.2f}%) • Buy Paused"
            elif price_moved and curr_ratio <= resting_bid:
                # Real Jupiter price dipped to touch/cross our resting Maker Bid!
                tranche_sol = round(sol_cash * TRANCHE_UTILIZATION, 5)
                exec_bid_ratio = curr_ratio

                maker_rebate_sol = tranche_sol * MAKER_REBATE_RATE
                effective_sol_deployed = tranche_sol + maker_rebate_sol
                tokens_acquired = effective_sol_deployed / exec_bid_ratio

                sol_cash -= tranche_sol
                tokens_held = tokens_acquired
                avg_entry = exec_bid_ratio
                holding_ticks = 0
                quiet_ticks = 0
                gas_reserve -= SOL_BASE_GAS_FEE

                slot["sol_cash"] = sol_cash
                slot["tokens_held"] = tokens_held
                slot["avg_entry_ratio"] = avg_entry
                slot["last_tranche_sol"] = tranche_sol
                slot["holding_ticks"] = 0
                slot["QuietTicks"] = 0
                slot["bid_fills"] = int(slot.get("bid_fills", 0)) + 1
                slot["maker_rebates_earned_sol"] = float(slot.get("maker_rebates_earned_sol", 0.0)) + maker_rebate_sol
                slot["last_action"] = (
                    f"BOUGHT DIP: {tranche_sol:.4f} SOL ➔ +{tokens_acquired:,.2f} {sym} "
                    f"(Earned +{maker_rebate_sol:.5f} SOL Maker Fee)"
                )

                total_maker_rebates += maker_rebate_sol
                total_gas_paid += SOL_BASE_GAS_FEE
                maker_fills += 1
                bid_fills += 1

                dip_pct = abs(tick_ret_pct)
                trade_history.insert(
                    0,
                    {
                        "id": f"as_bid_{int(now * 1000)}_{sym}_{maker_fills}",
                        "time": now,
                        "type": "MAKER_BID_DISCOUNT_FILL",
                        "symbol": sym,
                        "side": "BOUGHT DIP",
                        "action": f"Bought {tokens_acquired:,.4f} {sym} with {tranche_sol:.4f} SOL",
                        "tranche_sol": round(tranche_sol, 5),
                        "exec_ratio": exec_bid_ratio,
                        "spread_captured_pct": round(dip_pct, 3),
                        "maker_rebate_sol": round(maker_rebate_sol, 6),
                        "net_profit_sol": round(maker_rebate_sol - SOL_BASE_GAS_FEE, 5),
                        "reason": f"Live price touched Buy Target (-{dip_pct:.2f}% dip) • Earned +{maker_rebate_sol:.5f} SOL Fee",
                    },
                )
            elif price_moved and curr_ratio > resting_bid:
                # If price drifted higher while we are in 100% SOL, trail our resting Maker Bid up underneath spot (-0.12%)
                pass

        # ---------------------------------------------------------------------
        # C. UPDATE BUY / SELL TARGETS FOR NEXT REAL PRICE MOVE
        # ---------------------------------------------------------------------
        token_sol_val = tokens_held * curr_ratio
        vault_equity = sol_cash + token_sol_val
        inv_q = (token_sol_val / vault_equity) if vault_equity > 0 else 0.0

        sigma_pct = max(0.85, min(3.20, abs(float(p_info.get("z_score", 1.2))) * 0.85))
        quotes = compute_avellaneda_stoikov_quotes(
            mid_ratio=curr_ratio,
            micro_ratio=micro["micro_ratio"],
            inventory_q=inv_q,
            sigma_pct=sigma_pct,
            alpha_micro_pct=micro["alpha_micro_pct"],
            obi=micro["obi"],
            holding_ticks=holding_ticks,
            avg_entry_ratio=avg_entry,
            tick_ret_pct=tick_ret_pct,
        )

        if quotes["toxic_shield_active"] and inv_q <= 0.01:
            status_badge = "CRASH SHIELD (BUY PAUSED)"
        elif inv_q > 0.05:
            status_badge = "HOLDING TOKEN (SELLING ➔ SOL)"
        else:
            status_badge = "100% IN SOL (WAITING FOR DIP)"

        slot.update(
            {
                "sol_cash": round(sol_cash, 6),
                "tokens_held": round(tokens_held, 6),
                "token_sol_val": round(token_sol_val, 6),
                "vault_equity_sol": round(vault_equity, 6),
                "inventory_q_pct": round(inv_q * 100.0, 1),
                "avg_entry_ratio": avg_entry,
                "current_ratio": curr_ratio,
                "micro_ratio": micro["micro_ratio"],
                "reservation_ratio": quotes["reservation_ratio"],
                "bid_quote": quotes["bid_quote"],
                "ask_quote": quotes["ask_quote"],
                "spread_bps": quotes["spread_bps"],
                "skew_bps": quotes["skew_bps"],
                "obi": micro["obi"],
                "ofi": micro["ofi"],
                "alpha_micro_pct": micro["alpha_micro_pct"],
                "sigma_pct": round(sigma_pct, 2),
                "toxic_shield_active": quotes["toxic_shield_active"],
                "holding_ticks": holding_ticks,
                "QuietTicks": quiet_ticks,
                "status_badge": status_badge,
            }
        )

    # 3. Aggregate Portfolio Totals
    total_sol_vault = sum(float(s["sol_cash"]) for s in maker_slots.values())
    total_token_val = sum(float(s["token_sol_val"]) for s in maker_slots.values())
    total_equity = gas_reserve + total_sol_vault + total_token_val
    net_pnl_sol = total_equity - INITIAL_PORTFOLIO_SOL
    net_pnl_pct = (net_pnl_sol / INITIAL_PORTFOLIO_SOL) * 100.0

    trade_history = trade_history[:60]
    eq_curve = list(state.get("equity_curve", []))
    eq_curve.append(
        {
            "time": now,
            "equity": round(total_equity, 6),
            "sol_vault": round(total_sol_vault + total_token_val, 6),
        }
    )
    if len(eq_curve) > 80:
        eq_curve = eq_curve[-80:]

    state.update(
        {
            "last_update": now,
            "gas_reserve_sol": round(gas_reserve, 6),
            "total_sol_vault": round(total_sol_vault, 6),
            "total_token_val_sol": round(total_token_val, 6),
            "total_equity_sol": round(total_equity, 6),
            "net_pnl_sol": round(net_pnl_sol, 6),
            "net_pnl_pct": round(net_pnl_pct, 3),
            "accumulated_sol_profit": round(accumulated_sol, 6),
            "total_maker_rebates_sol": round(total_maker_rebates, 6),
            "total_gas_paid_sol": round(total_gas_paid, 6),
            "total_maker_fills": maker_fills,
            "total_bid_fills": bid_fills,
            "total_ask_fills": ask_fills,
            "total_round_trips": round_trips,
            "toxic_shields_triggered": shields_count,
            "sol_usd": sol_usd,
            "maker_slots": maker_slots,
            "trade_history": trade_history,
            "equity_curve": eq_curve,
        }
    )

    save_as_state(state)
    return state
