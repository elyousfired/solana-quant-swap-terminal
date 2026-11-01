// Solana Quant Swap Terminal - Frontend Logic

let currentTab = 'lst';

function switchTab(tabId) {
  currentTab = tabId;
  
  // Update buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('tab-active');
    btn.classList.add('text-gray-400');
  });
  
  const activeBtn = document.getElementById(`tab-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('tab-active');
    activeBtn.classList.remove('text-gray-400');
  }

  // Update pages
  document.querySelectorAll('.tab-page').forEach(page => {
    page.classList.add('hidden');
  });
  
  const activePage = document.getElementById(`page-${tabId}`);
  if (activePage) {
    activePage.classList.remove('hidden');
  }

  // Refresh data for active tab
  if (tabId === 'lst') loadLstDepeg();
  if (tabId === 'pairs') loadPairsRotation();
  if (tabId === 'loops') loadLoops();
  if (tabId === 'shannon') loadShannon();
}

// 1. Live Tickers Bar
async function loadTickers() {
  try {
    const res = await fetch('/api/prices');
    const data = await res.json();
    
    const container = document.getElementById('live-tickers');
    if (!container) return;

    let html = '';
    const symbols = ['SOL', 'JUP', 'RAY', 'JTO', 'KMNO', 'MET', 'PUMP', 'JitoSOL', 'mSOL', 'USDC'];
    
    symbols.forEach(sym => {
      if (data[sym]) {
        const item = data[sym];
        html += `
          <div class="flex items-center space-x-1 whitespace-nowrap">
            <span class="text-white font-bold">${sym}:</span>
            <span class="text-solana-green">$${item.price.toFixed(item.price < 1 ? 4 : 2)}</span>
          </div>
        `;
      }
    });
    container.innerHTML = html;
  } catch (err) {
    console.error('Error loading tickers:', err);
  }
}

// 2. Page 1: LST Depeg Arbitrage Terminal
async function loadLstDepeg() {
  try {
    const res = await fetch('/api/lst-depeg');
    const data = await res.json();
    
    document.getElementById('lst-sol-benchmark').innerText = `$${data.sol_benchmark_usd.toFixed(2)}`;

    const clock = document.getElementById('lst-live-clock');
    if (clock) {
      clock.innerText = new Date().toLocaleTimeString();
    }

    const container = document.getElementById('lst-cards');
    if (!container) return;

    let html = '';
    data.lst_assets.forEach(lst => {
      const isDiscount = lst.spread_pct <= -0.4;
      const isPremium = lst.spread_pct >= 0.4;
      
      let badgeColor = 'bg-gray-800 text-gray-400 border-gray-700';
      if (isDiscount) badgeColor = 'bg-solana-green/20 text-solana-green border-solana-green/40 font-bold';
      if (isPremium) badgeColor = 'bg-solana-purple/20 text-solana-purple border-solana-purple/40 font-bold';

      html += `
        <div class="bg-solana-dark border border-solana-border rounded-xl p-5 hover:border-solana-green/50 transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between">
              <span class="text-base font-bold text-white">${lst.token}</span>
              <span class="text-xs px-2.5 py-0.5 rounded-full border ${badgeColor}">
                ${isDiscount ? 'DISCOUNT DETECTED' : isPremium ? 'PREMIUM DETECTED' : 'FAIR VALUE'}
              </span>
            </div>
            
            <div class="mt-4 space-y-2 text-xs font-mono">
              <div class="flex justify-between">
                <span class="text-gray-400">DEX Market Ratio:</span>
                <span class="text-white font-bold">${lst.market_ratio_sol.toFixed(4)} SOL</span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-400">True Staking NAV:</span>
                <span class="text-solana-green font-bold">${lst.true_nav_ratio_sol.toFixed(4)} SOL</span>
              </div>
              <div class="flex justify-between border-t border-solana-border/50 pt-2">
                <span class="text-gray-400">Spread Divergence:</span>
                <span class="${isDiscount ? 'text-solana-green' : isPremium ? 'text-solana-purple' : 'text-gray-300'} font-bold">
                  ${lst.spread_pct.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>

          <div class="mt-5 pt-3 border-t border-solana-border/50">
            <div class="text-xs text-gray-400 mb-2 truncate">
              Action: <span class="text-white">${lst.action}</span>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="triggerSimulateSwap('SOL', '${lst.token}', 1.0)" class="flex-1 py-2 bg-solana-card hover:bg-solana-border text-solana-green border border-solana-green/30 rounded-lg text-xs font-bold transition">
                Simulate
              </button>
              <a href="https://jup.ag/swap/SOL-${lst.token}" target="_blank" rel="noopener noreferrer" class="px-3 py-2 bg-solana-purple/20 hover:bg-solana-purple/30 text-solana-purple border border-solana-purple/30 rounded-lg text-xs font-bold transition flex items-center gap-1">
                Trade on Jup ↗
              </a>
            </div>
          </div>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    console.error('Error loading LST depeg data:', err);
  }
}

function formatRatio(r) {
  if (!r || isNaN(r)) return '0.000000';
  if (r >= 0.001) return r.toFixed(6);
  return r.toFixed(8);
}

// 3. Page 2: Pairs Z-Score Rotation
async function loadPairsRotation() {
  try {
    const res = await fetch('/api/pairs-rotation');
    const pairs = await res.json();

    const clock = document.getElementById('pairs-live-clock');
    if (clock) {
      clock.innerText = new Date().toLocaleTimeString();
    }

    const tbody = document.getElementById('pairs-table-body');
    if (!tbody) return;

    let html = '';
    pairs.forEach(p => {
      const isExtreme = Math.abs(p.z_score) >= 2.0;
      const zColor = p.z_score >= 2.0 ? 'text-solana-purple' : p.z_score <= -2.0 ? 'text-solana-green' : 'text-gray-300';

      // Determine correct swap direction according to statistical signal
      const inToken = p.z_score <= -2.0 ? p.quote_token : p.base_token;
      const outToken = p.z_score <= -2.0 ? p.base_token : p.quote_token;
      const jupSwapUrl = `https://jup.ag/swap/${inToken}-${outToken}`;

      html += `
        <tr class="hover:bg-solana-dark/40 transition">
          <td class="py-3 px-4 font-bold text-white">${p.pair}</td>
          <td class="py-3 px-4 text-gray-300 font-mono">${formatRatio(p.current_ratio)}</td>
          <td class="py-3 px-4 font-bold ${zColor}">${p.z_score >= 0 ? '+' : ''}${p.z_score.toFixed(2)}σ</td>
          <td class="py-3 px-4 text-gray-400">${p.ou_half_life_hours}h</td>
          <td class="py-3 px-4">
            <span class="px-2 py-0.5 rounded text-[10px] ${isExtreme ? 'bg-solana-green/20 text-solana-green border border-solana-green/30 font-bold' : 'bg-gray-800 text-gray-400'}">
              ${p.signal}
            </span>
          </td>
          <td class="py-3 px-4 font-bold text-solana-green">${p.target_yield_pct > 0 ? '+' + p.target_yield_pct.toFixed(2) + '%' : '-'}</td>
          <td class="py-3 px-4 text-right">
            <div class="flex items-center justify-end gap-2">
              <button onclick="triggerSimulateSwap('${inToken}', '${outToken}', 10.0)" class="px-2.5 py-1 bg-solana-card hover:bg-solana-border text-solana-green border border-solana-green/30 rounded text-xs transition" title="Test Quote in Live Simulator">
                Simulate
              </button>
              <a href="${jupSwapUrl}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 bg-solana-purple/20 hover:bg-solana-purple/30 text-solana-purple border border-solana-purple/30 rounded text-xs transition font-bold flex items-center gap-1" title="Execute Live Swap on Jupiter DEX">
                Trade on Jup ↗
              </a>
            </div>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (err) {
    console.error('Error loading pairs rotation:', err);
  }
}

// 4. Page 3: Circular Multi-Hop Loops
async function loadLoops() {
  try {
    const res = await fetch('/api/circular-loops');
    const data = await res.json();

    const clock = document.getElementById('loops-live-clock');
    if (clock) {
      clock.innerText = new Date().toLocaleTimeString();
    }

    const container = document.getElementById('loops-container');
    if (!container) return;

    let html = '';
    data.verified_loops.forEach((loop, idx) => {
      // Determine entry leg tokens
      const pathTokens = loop.path.split(' -> ');
      const inTok = pathTokens[0] || 'SOL';
      const outTok = pathTokens[1] || 'JUP';

      html += `
        <div class="bg-solana-dark border border-solana-border rounded-xl p-5 hover:border-cyan-500/50 transition flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between">
              <span class="font-bold text-white text-sm">Path #${idx+1}</span>
              <span class="text-xs px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 font-bold">
                +${loop.net_profit_pct.toFixed(2)}% Net
              </span>
            </div>
            <div class="text-xs font-mono text-cyan-300 font-bold mt-2">
              ${loop.path}
            </div>

            <div class="mt-4 space-y-1.5 text-xs text-gray-400 font-mono">
              ${loop.legs.map((leg, lIdx) => `<div>Leg ${lIdx+1}: <span class="text-gray-300">${leg}</span></div>`).join('')}
            </div>
          </div>

          <div class="mt-5 pt-3 border-t border-solana-border/50">
            <div class="flex justify-between items-center text-xs text-gray-400 font-mono mb-2">
              <span>Latency: ${loop.latency_ms} ms</span>
              <span class="text-solana-green">Jito Bundle Verified</span>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="triggerSimulateSwap('${inTok}', '${outTok}', 1.0)" class="flex-1 py-1.5 bg-solana-card hover:bg-solana-border text-cyan-400 border border-cyan-500/30 rounded-lg text-xs font-bold transition">
                Simulate Route
              </button>
              <a href="https://jup.ag/swap/${inTok}-${outTok}" target="_blank" rel="noopener noreferrer" class="px-3 py-1.5 bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/30 rounded-lg text-xs font-bold transition flex items-center gap-1">
                Trade on Jup ↗
              </a>
            </div>
          </div>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (err) {
    console.error('Error loading circular loops:', err);
  }
}

function refreshLoops() {
  loadLoops();
}

// 5. Page 4: Shannon's Demon Volatility Harvester Matrix (All Pairs Live)
let currentShannonPair = "ALL";

function onShannonPairChange() {
  loadShannon("ALL");
}

async function loadShannon(pair = "ALL") {
  try {
    const res = await fetch(`/api/shannon-demon?pair=${encodeURIComponent(pair)}`);
    const data = await res.json();

    const clock = document.getElementById('shannon-live-clock');
    if (clock) {
      clock.innerText = new Date().toLocaleTimeString();
    }

    const container = document.getElementById('shannon-dashboard');
    if (!container) return;

    const pairsList = data.active_pairs || (data.pair ? [data] : []);

    let html = '';
    pairsList.forEach(p => {
      const tokenA = p.token_a || "SOL";
      const tokenB = p.token_b || "JUP";
      const weightA = p.current_weights?.token_a !== undefined ? p.current_weights.token_a : 50.0;
      const weightB = p.current_weights?.token_b !== undefined ? p.current_weights.token_b : 50.0;
      const isRebalance = p.action_required;
      const drift = p.drift_pct !== undefined ? p.drift_pct : 0.0;
      const stats = p.historical_stats || {};

      html += `
        <div class="bg-solana-dark border ${isRebalance ? 'border-amber-500/50 shadow-lg shadow-amber-500/5' : 'border-solana-border'} rounded-2xl p-5 flex flex-col justify-between hover:border-amber-400/50 transition">
          <div>
            <!-- Header -->
            <div class="flex items-center justify-between pb-3 border-b border-solana-border/50">
              <div class="flex items-center gap-2">
                <span class="font-bold text-white text-base">${p.pair}</span>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded ${isRebalance ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse font-bold' : 'bg-solana-card text-gray-400 border border-solana-border'}">
                  ${isRebalance ? 'REBALANCE DUE' : 'BALANCED'}
                </span>
              </div>
              <span class="text-xs font-mono font-bold ${isRebalance ? 'text-amber-400' : 'text-solana-green'}">
                Drift: ${isRebalance ? '+' : ''}${drift}%
              </span>
            </div>

            <!-- Allocation Bars -->
            <div class="mt-4 space-y-3">
              <div>
                <div class="flex justify-between text-xs font-mono mb-1">
                  <span class="text-solana-green font-bold">${tokenA}: ${weightA}%</span>
                  <span class="text-gray-400">Target: 50.0%</span>
                </div>
                <div class="w-full bg-gray-800 rounded-full h-2.5">
                  <div class="bg-solana-green h-2.5 rounded-full transition-all duration-500" style="width: ${weightA}%"></div>
                </div>
              </div>

              <div>
                <div class="flex justify-between text-xs font-mono mb-1">
                  <span class="text-solana-purple font-bold">${tokenB}: ${weightB}%</span>
                  <span class="text-gray-400">Target: 50.0%</span>
                </div>
                <div class="w-full bg-gray-800 rounded-full h-2.5">
                  <div class="bg-solana-purple h-2.5 rounded-full transition-all duration-500" style="width: ${weightB}%"></div>
                </div>
              </div>
            </div>

            <!-- Recommended Action Box -->
            <div class="mt-4 p-3 rounded-xl ${isRebalance ? 'bg-amber-500/10 border-amber-500/30 text-amber-300' : 'bg-solana-green/10 border-solana-green/30 text-solana-green'} border text-xs font-mono leading-relaxed">
              <span class="font-bold mr-1">${isRebalance ? '⚠️' : '✅'}</span> ${p.recommended_swap}
            </div>

            <!-- Stats Grid -->
            <div class="grid grid-cols-3 gap-2 mt-4 text-[11px] font-mono">
              <div class="bg-solana-card/60 p-2 rounded-lg border border-solana-border text-center">
                <div class="text-gray-400 text-[10px]">Cycles</div>
                <div class="font-bold text-white mt-0.5">${stats.total_cycles_completed || '-'}</div>
              </div>
              <div class="bg-solana-card/60 p-2 rounded-lg border border-solana-border text-center">
                <div class="text-gray-400 text-[10px]">Alpha</div>
                <div class="font-bold text-solana-green mt-0.5">+${stats.cumulative_harvested_alpha_pct || 0}%</div>
              </div>
              <div class="bg-solana-card/60 p-2 rounded-lg border border-solana-border text-center">
                <div class="text-gray-400 text-[10px]">Vol (σ)</div>
                <div class="font-bold text-amber-400 mt-0.5">${stats.annualized_volatility || '-'}</div>
              </div>
            </div>
          </div>

          <!-- Dual Action Buttons -->
          <div class="flex items-center gap-2 mt-5 pt-3 border-t border-solana-border/50">
            <button onclick="triggerSimulateSwap('${tokenA}', '${tokenB}', 1.0)" class="flex-1 py-2 bg-solana-card hover:bg-solana-border text-amber-400 border border-amber-500/30 rounded-xl text-xs font-bold transition">
              Simulate
            </button>
            <a href="https://jup.ag/swap/${tokenA}-${tokenB}" target="_blank" rel="noopener noreferrer" class="px-3.5 py-2 bg-solana-purple/20 text-solana-purple hover:bg-solana-purple/30 border border-solana-purple/30 rounded-xl text-xs font-bold transition flex items-center gap-1">
              Trade on Jup ↗
            </a>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    console.error('Error loading Shannon data:', err);
  }
}

// 6. Interactive Live Swap Simulator
async function runSimulation() {
  const inToken = document.getElementById('sim-in-token').value;
  const outToken = document.getElementById('sim-out-token').value;
  const amount = parseFloat(document.getElementById('sim-amount').value) || 1.0;

  const resultBox = document.getElementById('sim-result');
  resultBox.classList.remove('hidden');
  resultBox.innerHTML = '<span class="text-gray-400">Requesting live quote from Jupiter api.jup.ag...</span>';

  try {
    const res = await fetch('/api/simulate-swap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_symbol: inToken,
        output_symbol: outToken,
        amount: amount
      })
    });
    
    const quote = await res.json();
    if (quote.error) {
      resultBox.innerHTML = `<span class="text-red-400">${quote.error}</span>`;
      return;
    }

    let routeHtml = '';
    if (quote.route_plan && quote.route_plan.length > 0) {
      routeHtml = quote.route_plan.map((leg, i) => {
        const info = leg.swapInfo || {};
        return `<div class="text-gray-400">  Leg ${i+1}: ${leg.percent}% through <span class="text-solana-green font-bold">${info.label || 'AMM'}</span> (In: ${info.inAmount}, Out: ${info.outAmount})</div>`;
      }).join('');
    }

    resultBox.innerHTML = `
      <div class="space-y-2">
        <div class="flex items-center justify-between border-b border-solana-border pb-2">
          <span class="text-white font-bold">Swap Route Result:</span>
          <span class="text-solana-green font-bold">Latency: ${quote.latency_ms.toFixed(2)} ms</span>
        </div>
        <div>Input: <span class="text-white font-bold">${quote.input_amount} ${quote.input_symbol}</span></div>
        <div>Output: <span class="text-solana-green font-bold text-sm">${quote.output_amount.toFixed(4)} ${quote.output_symbol}</span></div>
        <div>Price Impact: <span class="text-gray-300 font-bold">${quote.price_impact_pct.toFixed(4)}%</span></div>
        <div>Solana Slot Context: <span class="text-solana-purple">${quote.slot_context}</span></div>
        <div class="pt-2 border-t border-solana-border/50">
          <div class="text-gray-400 font-bold mb-1">Liquidity Pool Route Plan:</div>
          ${routeHtml}
        </div>
      </div>
    `;
  } catch (err) {
    resultBox.innerHTML = `<span class="text-red-400">Error connecting to simulator: ${err}</span>`;
  }
}

function triggerSimulateSwap(inSym, outSym, amount) {
  document.getElementById('sim-in-token').value = inSym;
  document.getElementById('sim-out-token').value = outSym;
  document.getElementById('sim-amount').value = amount;
  
  // Scroll to simulator
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
  runSimulation();
}

// Continuous Live Polling
function pollActiveTab() {
  loadTickers();
  if (currentTab === 'lst') loadLstDepeg();
  else if (currentTab === 'pairs') loadPairsRotation();
  else if (currentTab === 'loops') loadLoops();
  else if (currentTab === 'shannon') loadShannon();
}

// Initial boot
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  loadTickers();
  loadLstDepeg();
  
  // Real-time live auto-refresh every 2.5 seconds
  setInterval(pollActiveTab, 2500);
});
