// ============================================================================
// INDEPENDENT MODULE (BUILT FROM SCRATCH):
// Engine 5 — Avellaneda-Stoikov Smart Maker & Dynamic DLMM Bin Frontend
// ============================================================================

const AS_MAKER_STORAGE_KEY = 'solana_as_maker_state_v1';
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
    const raw = localStorage.getItem(AS_MAKER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.strategy === 'AVELLANEDA_STOIKOV_SMART_MAKER_V1') {
      return parsed;
    }
  } catch (e) {
    console.warn('Failed to parse saved AS Maker state:', e);
  }
  return null;
}

function saveAsMakerStateLocal(state) {
  if (!state || state.strategy !== 'AVELLANEDA_STOIKOV_SMART_MAKER_V1') return;
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
    if (validState && validState.strategy === 'AVELLANEDA_STOIKOV_SMART_MAKER_V1') {
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
    if (data && data.strategy === 'AVELLANEDA_STOIKOV_SMART_MAKER_V1') {
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
    asMakerStateCache = null;
    const res = await fetch('/api/as-maker/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data && data.strategy === 'AVELLANEDA_STOIKOV_SMART_MAKER_V1') {
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
      statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-solana-green animate-pulse"></span> MAKER QUOTING LIVE (2.5s)';
    } else {
      statusBadge.className = 'flex items-center gap-1.5 text-xs text-amber-400 font-mono bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full';
      statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-400"></span> QUOTES PAUSED';
    }
  }
  if (toggleBtn) {
    toggleBtn.innerText = isRunning ? 'Pause Maker Engine' : 'Resume Maker Engine';
    toggleBtn.className = isRunning
      ? 'px-3 py-1.5 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-xl text-xs font-mono font-bold hover:bg-amber-500/30 transition'
      : 'px-3 py-1.5 bg-solana-green/20 text-solana-green border border-solana-green/40 rounded-xl text-xs font-mono font-bold hover:bg-solana-green/30 transition';
  }

  // Top KPI 1: Total Equity & Net PnL
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

  // Top KPI 2: Accumulated Pure SOL Profit (Closed Round-Trips)
  const accSol = Number(state.accumulated_sol_profit || 0.0);
  const accUsd = accSol * solUsd;
  const elAccSol = document.getElementById('as-kpi-acc-sol');
  if (elAccSol) {
    elAccSol.innerHTML = `+${accSol.toFixed(5)} SOL <span class="text-xs font-normal text-emerald-300/80">(+$${accUsd.toFixed(3)} USD)</span>`;
  }
  const elRoundTrips = document.getElementById('as-kpi-round-trips');
  if (elRoundTrips) {
    elRoundTrips.innerText = `${state.total_round_trips || 0} Full Cycles (Bid: ${state.total_bid_fills || 0} | Ask: ${state.total_ask_fills || 0})`;
  }

  // Top KPI 3: Maker Rebates & DLMM Dynamic Fees EARNED
  const rebatesSol = Number(state.total_maker_rebates_sol || 0.0);
  const rebatesUsd = rebatesSol * solUsd;
  const gasPaidSol = Number(state.total_gas_paid_sol || 0.0);
  const elRebates = document.getElementById('as-kpi-rebates');
  if (elRebates) {
    elRebates.innerHTML = `+${rebatesSol.toFixed(5)} SOL <span class="text-xs font-normal text-cyan-300/80">(+$${rebatesUsd.toFixed(3)} USD)</span>`;
  }
  const elFeeComparison = document.getElementById('as-kpi-fee-vs-taker');
  if (elFeeComparison) {
    const netFeeEdge = rebatesSol - gasPaidSol;
    elFeeComparison.innerText = `Gas Paid: -${gasPaidSol.toFixed(5)} SOL | Net Fee Edge: +${netFeeEdge.toFixed(5)} SOL`;
  }

  // Top KPI 4: SOL Cash Vault vs Inventory Exposure + Toxic Shields
  const solVault = Number(state.total_sol_vault || 0.96);
  const tokVal = Number(state.total_token_val_sol || 0.0);
  const shields = Number(state.toxic_shields_triggered || 0);
  const elVaultCash = document.getElementById('as-kpi-vault-cash');
  if (elVaultCash) {
    elVaultCash.innerHTML = `${solVault.toFixed(5)} SOL <span class="text-xs font-normal text-gray-400">($${(solVault * solUsd).toFixed(2)})</span>`;
  }
  const elInvSummary = document.getElementById('as-kpi-inv-summary');
  if (elInvSummary) {
    elInvSummary.innerText = `Active Inventory: ${tokVal.toFixed(4)} SOL | Toxic Dump Shields: ${shields}`;
  }

  // Render 6 Maker Vault Cards
  const cardsContainer = document.getElementById('as-maker-cards-grid');
  if (cardsContainer && state.maker_slots) {
    const order = ['JUP', 'RAY', 'JTO', 'KMNO', 'MET', 'PUMP'];
    let html = '';

    order.forEach(sym => {
      const slot = state.maker_slots[sym];
      if (!slot) return;

      const invQ = Number(slot.inventory_q_pct || 0.0);
      const hasInventory = Number(slot.tokens_held || 0.0) > 0.00001;
      const shieldOn = Boolean(slot.toxic_shield_active);
      const obi = Number(slot.obi || 0.0);
      const ofi = Number(slot.ofi || 0.0);
      const alphaMicro = Number(slot.alpha_micro_pct || 0.0);

      let cardBorder = 'border-solana-border hover:border-solana-green/40';
      let badgeClass = 'bg-solana-green/15 text-solana-green border-solana-green/30';
      if (shieldOn && !hasInventory) {
        cardBorder = 'border-red-500/40 bg-red-950/10';
        badgeClass = 'bg-red-500/20 text-red-300 border-red-500/40';
      } else if (hasInventory) {
        cardBorder = 'border-amber-400/50 bg-amber-950/10';
        badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse';
      }

      const obiPctBar = Math.min(100, Math.max(0, ((obi + 1.0) / 2.0) * 100));
      const obiColor = obi >= 0.10 ? 'text-solana-green' : obi <= -0.15 ? 'text-red-400' : 'text-gray-300';
      const slotProfit = Number(slot.accumulated_sol_profit || 0.0);
      const slotRebate = Number(slot.maker_rebates_earned_sol || 0.0);

      html += `
        <div class="bg-solana-dark border ${cardBorder} rounded-2xl p-4 transition-all flex flex-col justify-between space-y-3">
          <div>
            <!-- Header -->
            <div class="flex items-center justify-between border-b border-solana-border/60 pb-2.5">
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-base font-bold text-white font-mono">${sym} / SOL</span>
                  <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-solana-purple/15 text-solana-purple border border-solana-purple/30">
                    $${formatUsdPrice(slot.token_usd)}
                  </span>
                </div>
                <div class="text-[10px] text-gray-400 font-mono mt-0.5">${slot.venue || 'Meteora DLMM + Phoenix CLOB'}</div>
              </div>
              <span class="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full border ${badgeClass}">
                ${slot.status_badge}
              </span>
            </div>

            <!-- Vault SOL Cash vs Active Inventory -->
            <div class="grid grid-cols-2 gap-2 mt-3 bg-black/30 p-2.5 rounded-xl border border-solana-border/50 font-mono text-xs">
              <div>
                <div class="text-[10px] text-gray-400">PURE SOL IN VAULT</div>
                <div class="text-solana-green font-bold text-sm">${Number(slot.sol_cash).toFixed(5)} SOL</div>
                <div class="text-[10px] text-gray-500">Init: ${Number(slot.initial_sol).toFixed(4)} SOL</div>
              </div>
              <div class="text-right">
                <div class="text-[10px] text-gray-400">INVENTORY (q = ${invQ.toFixed(0)}%)</div>
                <div class="${hasInventory ? 'text-amber-300 font-bold' : 'text-gray-400'} text-sm">
                  ${hasInventory ? `${formatAsTokenQty(slot.tokens_held)} ${sym}` : '0.0000 (100% SOL)'}
                </div>
                <div class="text-[10px] text-gray-500">Val: ${Number(slot.token_sol_val).toFixed(5)} SOL</div>
              </div>
            </div>

            <!-- Avellaneda-Stoikov Live Quote Ladder -->
            <div class="mt-3 space-y-1.5 font-mono text-xs bg-solana-card/70 p-2.5 rounded-xl border border-solana-border/60">
              <div class="flex items-center justify-between text-[10px] text-gray-400 border-b border-solana-border/40 pb-1">
                <span>AVELLANEDA-STOIKOV LADDER</span>
                <span>Spread: <strong class="text-cyan-300">${Number(slot.spread_bps).toFixed(1)} bps</strong> | Skew: <strong class="${Number(slot.skew_bps) < 0 ? 'text-amber-400' : 'text-solana-green'}">${Number(slot.skew_bps).toFixed(1)} bps</strong></span>
              </div>

              <div class="flex justify-between items-center">
                <span class="text-gray-400 text-[11px]">Maker Ask (Sell -> SOL):</span>
                <span class="text-emerald-400 font-bold">${formatAsRatio(slot.ask_quote)} SOL</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-400 text-[11px]">Micro-Price (P_micro):</span>
                <span class="text-cyan-300">${formatAsRatio(slot.micro_ratio)} SOL</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-400 text-[11px]">Reservation r(s, q):</span>
                <span class="text-solana-purple font-semibold">${formatAsRatio(slot.reservation_ratio)} SOL</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-400 text-[11px]">Maker Bid (Buy Dip):</span>
                <span class="${shieldOn ? 'text-red-400 line-through' : 'text-solana-green font-bold'}">${formatAsRatio(slot.bid_quote)} SOL</span>
              </div>
            </div>

            <!-- Orderbook Microstructure (OBI / OFI / Alpha) -->
            <div class="mt-3 font-mono text-[11px]">
              <div class="flex justify-between items-center mb-1">
                <span class="text-gray-400">L1 Book OBI: <strong class="${obiColor}">${obi >= 0 ? '+' : ''}${obi.toFixed(2)}</strong></span>
                <span class="text-gray-400">OFI: <strong class="text-white">${ofi >= 0 ? '+' : ''}${ofi.toFixed(2)}</strong></span>
                <span class="text-gray-400">α_micro: <strong class="${alphaMicro >= 0 ? 'text-solana-green' : 'text-red-400'}">${alphaMicro >= 0 ? '+' : ''}${alphaMicro.toFixed(2)}%</strong></span>
              </div>
              <div class="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden flex">
                <div class="bg-gradient-to-r from-red-500 via-amber-400 to-solana-green h-full transition-all duration-300" style="width: ${obiPctBar}%"></div>
              </div>
            </div>
          </div>

          <!-- Footer Metrics -->
          <div class="pt-2 border-t border-solana-border/60 flex flex-col gap-1 font-mono text-[11px]">
            <div class="flex items-center justify-between">
              <span class="text-gray-400">Cycles: <strong class="text-white">${slot.round_trips || 0}</strong> (B:${slot.bid_fills || 0}/A:${slot.ask_fills || 0})</span>
              <span class="text-cyan-300">Rebates: +${slotRebate.toFixed(5)} SOL</span>
              <span class="text-solana-green font-bold">Net: +${slotProfit.toFixed(5)} SOL</span>
            </div>
            <div class="text-[10px] text-gray-400 truncate" title="${slot.last_action || ''}">
              ⚡ ${slot.last_action || 'Quoting resting Post-Only Bid...'}
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
          <td colspan="7" class="text-center py-6 text-gray-500 font-mono text-xs">
            Waiting for first Maker Bid fill on Meteora DLMM / Phoenix CLOB...
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = history.slice(0, 30).map(tx => {
        const dt = new Date((tx.time || Date.now() / 1000) * 1000).toLocaleTimeString();
        const isAsk = tx.type === 'MAKER_ASK_SOL_HARVEST';
        const badge = isAsk
          ? '<span class="px-2 py-0.5 rounded bg-solana-green/20 text-solana-green border border-solana-green/40 font-bold text-[10px]">ASK FILL ➔ SOL</span>'
          : '<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold text-[10px]">BID FILL (DISCOUNT)</span>';

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
