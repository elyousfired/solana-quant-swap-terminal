// ============================================================================
// INDEPENDENT MODULE (BUILT FROM SCRATCH - V2 REAL EXECUTION & CLEAR UI):
// Engine 5 — Smart Maker & Dynamic DLMM Bin Frontend
// ============================================================================

const AS_MAKER_STORAGE_KEY = 'solana_as_maker_state_v2';
const AS_STRATEGY_ID = 'AVELLANEDA_STOIKOV_SMART_MAKER_V2';
let asMakerStateCache = null;
let asMakerTickInterval = null;
let asMakerTickInFlight = false;

function formatAsRatio(r) {
  if (!r || isNaN(r)) return '0.00000000';
  if (r >= 10.0) return r.toFixed(4);
  if (r >= 1.0) return r.toFixed(5);
  if (r >= 0.01) return r.toFixed(7);
  if (r >= 0.001) return r.toFixed(8);
  if (r >= 0.0001) return r.toFixed(9);
  return r.toFixed(10);
}

function formatAsTokenQty(q) {
  if (q === undefined || q === null || isNaN(q)) return '0.0000';
  const absQ = Math.abs(q);
  const dec = absQ >= 1000 ? 2 : absQ >= 100 ? 3 : absQ >= 10 ? 4 : 5;
  return q.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function getSavedAsMakerState() {
  try {
    // Clean up old v1 state if present
    localStorage.removeItem('solana_as_maker_state_v1');
    const raw = localStorage.getItem(AS_MAKER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.strategy === AS_STRATEGY_ID) {
      return parsed;
    }
  } catch (e) {
    console.warn('Failed to parse saved AS Maker state:', e);
  }
  return null;
}

function saveAsMakerStateLocal(state) {
  if (!state || state.strategy !== AS_STRATEGY_ID) return;
  asMakerStateCache = state;
  try {
    localStorage.setItem(AS_MAKER_STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save AS Maker state to localStorage:', e);
  }
}

async function loadAsMakerPage() {
  const cached = asMakerStateCache || getSavedAsMakerState();
  if (cached) {
    renderAsMakerUI(cached);
  }
  await triggerAsMakerTick();
  startAsMakerLoop();
}

function startAsMakerLoop() {
  if (asMakerTickInterval) clearInterval(asMakerTickInterval);
  asMakerTickInterval = setInterval(async () => {
    if (typeof currentTab !== 'undefined' && currentTab === 'asmaker') {
      await triggerAsMakerTick();
    }
  }, 2500);
}

async function triggerAsMakerTick() {
  if (asMakerTickInFlight) return;
  asMakerTickInFlight = true;
  try {
    const clientState = asMakerStateCache || getSavedAsMakerState();
    const res = await fetch('/api/as-maker/tick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: clientState })
    });
    const data = await res.json();
    const validState = data.strategy ? data : data.state;
    if (validState && validState.strategy === AS_STRATEGY_ID) {
      saveAsMakerStateLocal(validState);
      renderAsMakerUI(validState);
    }
  } catch (err) {
    console.error('AS Maker tick error:', err);
  } finally {
    asMakerTickInFlight = false;
  }
}

async function toggleAsMakerBot() {
  try {
    const clientState = asMakerStateCache || getSavedAsMakerState();
    const res = await fetch('/api/as-maker/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: clientState })
    });
    const data = await res.json();
    if (data && data.strategy === AS_STRATEGY_ID) {
      saveAsMakerStateLocal(data);
      renderAsMakerUI(data);
    }
  } catch (err) {
    console.error('Error toggling AS Maker bot:', err);
  }
}

async function resetAsMakerBot() {
  try {
    localStorage.removeItem(AS_MAKER_STORAGE_KEY);
    localStorage.removeItem('solana_as_maker_state_v1');
    asMakerStateCache = null;
    const res = await fetch('/api/as-maker/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data && data.strategy === AS_STRATEGY_ID) {
      saveAsMakerStateLocal(data);
      renderAsMakerUI(data);
    }
  } catch (err) {
    console.error('Error resetting AS Maker bot:', err);
  }
}

function renderAsMakerUI(state) {
  if (!state) return;

  const solUsd = Number(state.sol_usd || 84.5);
  const isRunning = Boolean(state.is_running);

  // Status badge & Toggle button
  const statusBadge = document.getElementById('as-bot-status-badge');
  const toggleBtn = document.getElementById('as-toggle-btn');
  if (statusBadge) {
    if (isRunning) {
      statusBadge.className = 'flex items-center gap-1.5 text-xs text-solana-green font-mono bg-solana-green/10 border border-solana-green/30 px-3 py-1 rounded-full';
      statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-solana-green animate-pulse"></span> LIVE REAL-PRICE EXECUTION';
    } else {
      statusBadge.className = 'flex items-center gap-1.5 text-xs text-amber-400 font-mono bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full';
      statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400"></span> BOT PAUSED';
    }
  }
  if (toggleBtn) {
    toggleBtn.innerText = isRunning ? 'Pause Bot' : 'Resume Bot';
    toggleBtn.className = isRunning
      ? 'px-3 py-1.5 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-xl text-xs font-mono font-bold hover:bg-amber-500/30 transition'
      : 'px-3 py-1.5 bg-solana-green/20 text-solana-green border border-solana-green/40 rounded-xl text-xs font-mono font-bold hover:bg-solana-green/30 transition';
  }

  // Top KPI 1: Total Wallet Value & Net Profit
  const totalEq = Number(state.total_equity_sol || 1.0);
  const netPnlSol = Number(state.net_pnl_sol || 0.0);
  const netPnlPct = Number(state.net_pnl_pct || 0.0);
  const netPnlUsd = netPnlSol * solUsd;
  const pnlSign = netPnlSol >= 0 ? '+' : '';
  const pnlColor = netPnlSol >= 0 ? 'text-solana-green' : 'text-red-400';

  const elEq = document.getElementById('as-kpi-equity');
  if (elEq) {
    elEq.innerHTML = `${totalEq.toFixed(5)} SOL <span class="text-xs font-normal text-gray-400">($${(totalEq * solUsd).toFixed(2)})</span>`;
  }
  const elPnl = document.getElementById('as-kpi-pnl');
  if (elPnl) {
    elPnl.className = `text-xs font-mono mt-1 font-bold ${pnlColor}`;
    elPnl.innerHTML = `${pnlSign}${netPnlSol.toFixed(5)} SOL (${pnlSign}${netPnlPct.toFixed(2)}%) <span class="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[10px]">${pnlSign}$${Math.abs(netPnlUsd).toFixed(3)} USD</span>`;
  }

  // Top KPI 2: Pure SOL Profit Locked in Vault
  const accSol = Number(state.accumulated_sol_profit || 0.0);
  const accUsd = accSol * solUsd;
  const elAccSol = document.getElementById('as-kpi-acc-sol');
  if (elAccSol) {
    elAccSol.innerHTML = `+${accSol.toFixed(5)} SOL <span class="text-xs font-normal text-emerald-300/80">(+$${accUsd.toFixed(3)} USD)</span>`;
  }
  const elRoundTrips = document.getElementById('as-kpi-round-trips');
  if (elRoundTrips) {
    elRoundTrips.innerText = `${state.total_round_trips || 0} Completed Cycles (Bought: ${state.total_bid_fills || 0} | Sold to SOL: ${state.total_ask_fills || 0})`;
  }

  // Top KPI 3: Maker Fees EARNED (vs Taker Fees)
  const rebatesSol = Number(state.total_maker_rebates_sol || 0.0);
  const rebatesUsd = rebatesSol * solUsd;
  const gasPaidSol = Number(state.total_gas_paid_sol || 0.0);
  const elRebates = document.getElementById('as-kpi-rebates');
  if (elRebates) {
    elRebates.innerHTML = `+${rebatesSol.toFixed(5)} SOL <span class="text-xs font-normal text-cyan-300/80">(+$${rebatesUsd.toFixed(3)} USD)</span>`;
  }
  const elFeeComparison = document.getElementById('as-kpi-fee-vs-taker');
  if (elFeeComparison) {
    elFeeComparison.innerText = `Solana Gas Paid: -${gasPaidSol.toFixed(5)} SOL • Zero (-0.15%) Taker Fee!`;
  }

  // Top KPI 4: Safe SOL in Cash vs Active Tokens
  const solVault = Number(state.total_sol_vault || 0.96);
  const tokVal = Number(state.total_token_val_sol || 0.0);
  const shields = Number(state.toxic_shields_triggered || 0);
  const elVaultCash = document.getElementById('as-kpi-vault-cash');
  if (elVaultCash) {
    elVaultCash.innerHTML = `${solVault.toFixed(5)} SOL <span class="text-xs font-normal text-gray-400">($${(solVault * solUsd).toFixed(2)})</span>`;
  }
  const elInvSummary = document.getElementById('as-kpi-inv-summary');
  if (elInvSummary) {
    elInvSummary.innerText = `In Tokens Now: ${tokVal.toFixed(4)} SOL | Crash Shields Triggered: ${shields}`;
  }

  // Render 6 Clear & Easy-to-Read Vault Cards
  const cardsContainer = document.getElementById('as-maker-cards-grid');
  if (cardsContainer && state.maker_slots) {
    const order = ['JUP', 'RAY', 'JTO', 'KMNO', 'MET', 'PUMP'];
    let html = '';

    order.forEach(sym => {
      const slot = state.maker_slots[sym];
      if (!slot) return;

      const hasInventory = Number(slot.tokens_held || 0.0) > 0.00001;
      const shieldOn = Boolean(slot.toxic_shield_active);
      const obi = Number(slot.obi || 0.0);
      const currRatio = Number(slot.current_ratio || 0.0);
      const buyTarget = Number(slot.bid_quote || 0.0);
      const sellTarget = Number(slot.ask_quote || 0.0);
      const boughtAt = Number(slot.avg_entry_ratio || 0.0);

      let cardBorder = 'border-solana-border hover:border-solana-green/40';
      let badgeClass = 'bg-solana-green/15 text-solana-green border-solana-green/30';
      let badgeText = '🟢 100% IN SOL (WAITING FOR DIP)';
      if (shieldOn && !hasInventory) {
        cardBorder = 'border-red-500/40 bg-red-950/10';
        badgeClass = 'bg-red-500/20 text-red-300 border-red-500/40';
        badgeText = '🛡️ CRASH SHIELD (BUY PAUSED)';
      } else if (hasInventory) {
        cardBorder = 'border-amber-400/50 bg-amber-950/10';
        badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse';
        badgeText = '🟡 HOLDING TOKEN (SELLING ➔ SOL)';
      }

      const obiPctBar = Math.min(100, Math.max(0, ((obi + 1.0) / 2.0) * 100));
      let marketMood = 'Balanced Orderbook (Safe to Quote)';
      let moodColor = 'text-gray-300';
      if (shieldOn) {
        marketMood = 'Heavy Selling Detected (Buy Paused)';
        moodColor = 'text-red-400 font-bold';
      } else if (obi >= 0.12) {
        marketMood = 'Strong Buying Pressure (Bullish)';
        moodColor = 'text-solana-green font-bold';
      }

      const slotProfit = Number(slot.accumulated_sol_profit || 0.0);
      const slotRebate = Number(slot.maker_rebates_earned_sol || 0.0);

      // Distance to Buy or Sell Target in %
      const distToBuyPct = currRatio > 0 ? (((buyTarget - currRatio) / currRatio) * 100.0) : 0.0;
      const distToSellPct = (hasInventory && boughtAt > 0) ? (((sellTarget - boughtAt) / boughtAt) * 100.0) : 0.0;

      html += `
        <div class="bg-solana-dark border ${cardBorder} rounded-2xl p-4 transition-all flex flex-col justify-between space-y-3">
          <div>
            <!-- Header -->
            <div class="flex items-center justify-between border-b border-solana-border/60 pb-2.5">
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-base font-bold text-white font-mono">${sym} Vault</span>
                  <span class="text-[11px] font-mono px-2 py-0.5 rounded bg-solana-purple/15 text-solana-purple border border-solana-purple/30">
                    $${formatUsdPrice(slot.token_usd)}
                  </span>
                </div>
                <div class="text-[10px] text-gray-400 font-mono mt-0.5">Starts with 0.16000 SOL • Zero Blind Buy</div>
              </div>
              <span class="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full border ${badgeClass}">
                ${badgeText}
              </span>
            </div>

            <!-- Box 1: What is inside this vault right now? -->
            <div class="grid grid-cols-2 gap-2 mt-3 bg-black/30 p-3 rounded-xl border border-solana-border/50 font-mono text-xs">
              <div>
                <div class="text-[10px] text-gray-400">SAFE SOL CASH</div>
                <div class="text-solana-green font-bold text-sm mt-0.5">${Number(slot.sol_cash).toFixed(5)} SOL</div>
                <div class="text-[10px] text-gray-500">Started: ${Number(slot.initial_sol).toFixed(4)} SOL</div>
              </div>
              <div class="text-right">
                <div class="text-[10px] text-gray-400">TOKENS HELD NOW</div>
                <div class="${hasInventory ? 'text-amber-300 font-bold' : 'text-gray-400'} text-sm mt-0.5">
                  ${hasInventory ? `${formatAsTokenQty(slot.tokens_held)} ${sym}` : `0 ${sym} (100% SOL)`}
                </div>
                <div class="text-[10px] text-gray-500">Worth: ${Number(slot.token_sol_val).toFixed(5)} SOL</div>
              </div>
            </div>

            <!-- Box 2: Clear Price & Target Ladder -->
            <div class="mt-3 space-y-2 font-mono text-xs bg-solana-card/70 p-3 rounded-xl border border-solana-border/60">
              <div class="flex justify-between items-center border-b border-solana-border/40 pb-1.5">
                <span class="text-gray-300 font-semibold">Current Live Price:</span>
                <span class="text-white font-bold text-sm">${formatAsRatio(currRatio)} SOL</span>
              </div>

              ${hasInventory ? `
                <div class="flex justify-between items-center">
                  <span class="text-gray-400">Bought At Price:</span>
                  <span class="text-amber-300 font-semibold">${formatAsRatio(boughtAt)} SOL</span>
                </div>
                <div class="flex justify-between items-center bg-solana-green/10 px-2 py-1 rounded border border-solana-green/30">
                  <span class="text-solana-green font-bold">🎯 Sell Target (➔ SOL):</span>
                  <span class="text-solana-green font-bold">${formatAsRatio(sellTarget)} SOL (+${distToSellPct.toFixed(2)}%)</span>
                </div>
              ` : `
                <div class="flex justify-between items-center ${shieldOn ? 'bg-red-500/10 border-red-500/30' : 'bg-cyan-500/10 border-cyan-500/30'} px-2 py-1 rounded border">
                  <span class="${shieldOn ? 'text-red-300' : 'text-cyan-300'} font-bold">
                    ${shieldOn ? '🛡️ Buy Target (Paused):' : '🎯 Buy Target (Dip):'}
                  </span>
                  <span class="${shieldOn ? 'text-red-400 line-through' : 'text-cyan-300 font-bold'}">
                    ${formatAsRatio(buyTarget)} SOL (${distToBuyPct.toFixed(2)}%)
                  </span>
                </div>
                <div class="flex justify-between items-center text-[11px]">
                  <span class="text-gray-400">Next Sell Target (➔ SOL):</span>
                  <span class="text-gray-300">${formatAsRatio(sellTarget)} SOL (+0.22% + Fee)</span>
                </div>
              `}
            </div>

            <!-- Box 3: Simple Market Pressure Status -->
            <div class="mt-3 font-mono text-[11px]">
              <div class="flex justify-between items-center mb-1">
                <span class="text-gray-400">Market Status:</span>
                <span class="${moodColor}">${marketMood}</span>
              </div>
              <div class="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden flex">
                <div class="bg-gradient-to-r from-red-500 via-amber-400 to-solana-green h-full transition-all duration-300" style="width: ${obiPctBar}%"></div>
              </div>
            </div>
          </div>

          <!-- Footer Summary -->
          <div class="pt-2.5 border-t border-solana-border/60 flex flex-col gap-1 font-mono text-[11px]">
            <div class="flex items-center justify-between">
              <span class="text-gray-400">Completed Cycles: <strong class="text-white">${slot.round_trips || 0}</strong></span>
              <span class="text-cyan-300">Fees Earned: +${slotRebate.toFixed(5)}</span>
              <span class="text-solana-green font-bold">SOL Profit: +${slotProfit.toFixed(5)}</span>
            </div>
            <div class="text-[10px] text-gray-400 truncate" title="${slot.last_action || ''}">
              ⚡ ${slot.last_action || 'Waiting for real live price to touch Buy Target...'}
            </div>
          </div>
        </div>
      `;
    });

    cardsContainer.innerHTML = html;
  }

  // Render Maker Execution Ledger
  const tbody = document.getElementById('as-maker-ledger-tbody');
  if (tbody) {
    const history = state.trade_history || [];
    if (history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-6 text-gray-400 font-mono text-xs">
            No trades executed yet — waiting for live Jupiter price to actually reach a Buy Target...
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = history.slice(0, 30).map(tx => {
        const dt = new Date((tx.time || Date.now() / 1000) * 1000).toLocaleTimeString();
        const isAsk = tx.type === 'MAKER_ASK_SOL_HARVEST';
        const badge = isAsk
          ? '<span class="px-2 py-0.5 rounded bg-solana-green/20 text-solana-green border border-solana-green/40 font-bold text-[10px]">SOLD ➔ SOL</span>'
          : '<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold text-[10px]">BOUGHT DIP</span>';

        const netSol = Number(tx.net_profit_sol || 0.0);
        const netUsd = netSol * solUsd;
        const rebateSol = Number(tx.maker_rebate_sol || 0.0);

        return `
          <tr class="border-b border-solana-border/40 hover:bg-white/[0.02] transition">
            <td class="py-2.5 px-3 text-gray-400">${dt}</td>
            <td class="py-2.5 px-3 font-bold text-white">${tx.symbol}</td>
            <td class="py-2.5 px-3">${badge}</td>
            <td class="py-2.5 px-3 text-gray-200">${tx.action}</td>
            <td class="py-2.5 px-3 text-right font-mono text-gray-300">${formatAsRatio(tx.exec_ratio)}</td>
            <td class="py-2.5 px-3 text-right font-mono text-cyan-300 font-semibold">+${rebateSol.toFixed(6)} SOL</td>
            <td class="py-2.5 px-3 text-right font-mono font-bold ${isAsk ? 'text-solana-green' : 'text-emerald-300'}">
              +${netSol.toFixed(5)} SOL
              <div class="text-[10px] font-normal text-gray-400">(+$${netUsd.toFixed(3)} USD)</div>
            </td>
          </tr>
        `;
      }).join('');
    }
  }
}

window.loadAsMakerPage = loadAsMakerPage;
window.toggleAsMakerBot = toggleAsMakerBot;
window.resetAsMakerBot = resetAsMakerBot;
window.triggerAsMakerTick = triggerAsMakerTick;
