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
  
  // Route both 'pairs' and 'shannon' to unified page-pairs container
  const targetPageId = (tabId === 'pairs' || tabId === 'shannon') ? 'page-pairs' : `page-${tabId}`;
  const activePage = document.getElementById(targetPageId);
  if (activePage) {
    activePage.classList.remove('hidden');
  }

  // Refresh data for active tab
  if (tabId === 'lst') loadLstDepeg();
  if (tabId === 'loops') loadLoops();
  if (tabId === 'pairs' || tabId === 'shannon') {
    loadShannon();
    loadPairsRotation();
    loadDemoState();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
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
  if (!r || isNaN(r)) return '0.0000';
  if (r >= 10.0) return r.toFixed(2);
  if (r >= 1.0) return r.toFixed(4);
  if (r >= 0.001) return r.toFixed(6);
  return r.toFixed(8);
}

function generateRatioSparkline(data, pairName, width = 280, height = 48) {
  if (!data || data.length < 2) {
    return `<div class="h-8 flex items-center justify-center text-[10px] text-gray-600 font-mono">Loading ratio...</div>`;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = (max - min) || (min * 0.005) || 1;

  const padY = 4;
  const usableH = height - (padY * 2);

  const points = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * width;
    const y = height - padY - ((val - min) / range) * usableH;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const pathD = `M ${points.join(' L ')}`;
  const areaD = `M ${points[0]} L ${points.join(' L ')} L ${width},${height} L 0,${height} Z`;

  const isUp = data[data.length - 1] >= data[0];
  const strokeColor = isUp ? '#14F195' : '#F59E0B';
  const cleanId = 'spark_' + pairName.replace(/[^a-zA-Z0-9]/g, '_') + '_' + width;

  const mean = data.reduce((a, b) => a + b, 0) / data.length;
  const meanY = (height - padY - ((mean - min) / range) * usableH).toFixed(1);

  const lastPt = points[points.length - 1].split(',');
  const lastX = lastPt[0];
  const lastY = lastPt[1];

  return `
    <svg viewBox="0 0 ${width} ${height}" class="w-full h-full overflow-visible" preserveAspectRatio="none">
      <defs>
        <linearGradient id="${cleanId}" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.30"/>
          <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <line x1="0" y1="${meanY}" x2="${width}" y2="${meanY}" stroke="#374151" stroke-dasharray="3,3" stroke-width="1"/>
      <path d="${areaD}" fill="url(#${cleanId})"/>
      <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="${lastX}" cy="${lastY}" r="3" fill="${strokeColor}"/>
    </svg>
  `;
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

      const sparkHtml = generateRatioSparkline(p.ratio_history || [], p.pair, 110, 26);
      const rChg = p.ratio_24h_change_pct !== undefined ? p.ratio_24h_change_pct : 0.0;
      const isRatioUp = rChg >= 0;

      // Human-readable clear signal badge matching exact quantitative logic
      let signalBadge = '';
      if (p.z_score >= 2.0) {
        signalBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-solana-purple/20 text-solana-purple border border-solana-purple/30">SWAP ${p.base_token} ➔ SOL</span>`;
      } else if (p.z_score <= -2.0) {
        signalBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-solana-green/20 text-solana-green border border-solana-green/30">SWAP SOL ➔ ${p.base_token}</span>`;
      } else {
        signalBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-800 text-gray-400 border border-gray-700">NEUTRAL (HOLD)</span>`;
      }

      // Target net gain badge (clear explanation of Neutral zone instead of confusing -)
      let yieldBadge = '';
      if (p.target_yield_pct > 0) {
        yieldBadge = `<span class="font-bold text-solana-green">+${p.target_yield_pct.toFixed(2)}%</span>`;
      } else {
        yieldBadge = `<span class="text-gray-500 font-mono text-[11px]" title="Z-Score is within ±2.0σ normal band. Entry trigger requires |Z| ≥ 2.0σ.">In Band (0.0%)</span>`;
      }

      html += `
        <tr class="hover:bg-solana-dark/40 transition">
          <!-- 1. Pair (SOL / Token) -->
          <td class="py-3 px-3 font-bold text-white whitespace-nowrap">
            <span class="text-sm">${p.pair}</span>
          </td>

          <!-- 2. 4H Trend Curve (vs SOL) -->
          <td class="py-3 px-3">
            <div class="flex items-center gap-2">
              <div class="w-28 h-7">
                ${sparkHtml}
              </div>
              <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${isRatioUp ? 'bg-solana-green/20 text-solana-green border border-solana-green/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'}">
                ${isRatioUp ? '+' : ''}${rChg.toFixed(1)}%
              </span>
            </div>
          </td>

          <!-- 3. Exchange Rate -->
          <td class="py-3 px-3 font-mono text-xs whitespace-nowrap">
            <div class="font-bold text-white">
              ${formatRatio(p.current_ratio)} SOL
            </div>
            <div class="text-[10px] text-gray-400">
              1 SOL = ${p.token_per_sol ? p.token_per_sol.toLocaleString() : '-'} ${p.base_token}
            </div>
          </td>

          <!-- 4. Z-Score Divergence -->
          <td class="py-3 px-3 font-bold font-mono ${zColor}">
            ${p.z_score >= 0 ? '+' : ''}${p.z_score.toFixed(2)}σ
          </td>

          <!-- 5. OU Half-Life -->
          <td class="py-3 px-3 text-gray-400 font-mono">
            ${p.ou_half_life_hours}h
          </td>

          <!-- 6. Signal -->
          <td class="py-3 px-3">
            ${signalBadge}
          </td>

          <!-- 7. Target Net Gain -->
          <td class="py-3 px-3 font-mono">
            ${yieldBadge}
          </td>

          <!-- 8. Execution & Trade -->
          <td class="py-3 px-3 text-right whitespace-nowrap">
            <div class="flex items-center justify-end gap-1.5">
              <button onclick="triggerSimulateSwap('${inToken}', '${outToken}', 10.0)" class="px-2.5 py-1 bg-solana-card hover:bg-solana-border text-solana-green border border-solana-green/30 rounded text-xs font-bold transition" title="Test Quote in Live Simulator">
                Simulate
              </button>
              <a href="${jupSwapUrl}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 bg-solana-purple/20 hover:bg-solana-purple/30 text-solana-purple border border-solana-purple/30 rounded text-xs font-bold transition flex items-center gap-1" title="Execute Live Swap on Jupiter DEX">
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

    const tbody = document.getElementById('shannon-table-body') || document.getElementById('shannon-dashboard');
    if (!tbody) return;

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
      const sparkHtml = generateRatioSparkline(p.ratio_history || [], p.pair, 110, 26);
      const ratioChg = p.ratio_24h_change_pct !== undefined ? p.ratio_24h_change_pct : 0.0;
      const isRatioUp = ratioChg >= 0;

      html += `
        <tr class="hover:bg-solana-dark/40 transition">
          <!-- 1. Pair -->
          <td class="py-3 px-3 font-bold text-white whitespace-nowrap">
            <span class="text-sm">${p.pair}</span>
          </td>

          <!-- 2. 4H Trend Curve (vs SOL) -->
          <td class="py-3 px-3">
            <div class="flex items-center gap-2">
              <div class="w-28 h-7">
                ${sparkHtml}
              </div>
              <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${isRatioUp ? 'bg-solana-green/20 text-solana-green border border-solana-green/30' : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'}">
                ${isRatioUp ? '+' : ''}${ratioChg.toFixed(1)}%
              </span>
            </div>
          </td>

          <!-- 3. Exchange Rate -->
          <td class="py-3 px-3 font-mono text-xs whitespace-nowrap">
            <div class="font-bold text-white">
              ${tokenB === 'USDC' ? '$' + formatRatio(p.current_ratio) : formatRatio(p.current_ratio) + ' SOL'}
            </div>
            <div class="text-[10px] text-gray-400">
              ${tokenB === 'USDC' ? 'SOL Spot' : '1 SOL = ' + (p.token_per_sol ? p.token_per_sol.toLocaleString() : '-') + ' ' + tokenB}
            </div>
          </td>

          <!-- 4. Balance (50/50 Dual Bar) -->
          <td class="py-3 px-3 min-w-[140px]">
            <div class="flex justify-between text-[10px] font-mono mb-1">
              <span class="text-solana-green font-bold">SOL: ${weightA}%</span>
              <span class="text-solana-purple font-bold">${tokenB}: ${weightB}%</span>
            </div>
            <div class="w-full bg-gray-800 rounded-full h-2 flex overflow-hidden">
              <div class="bg-solana-green h-2 transition-all duration-500" style="width: ${weightA}%"></div>
              <div class="bg-solana-purple h-2 transition-all duration-500" style="width: ${weightB}%"></div>
            </div>
          </td>

          <!-- 5. Drift -->
          <td class="py-3 px-3 whitespace-nowrap font-mono">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${isRebalance ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse' : 'bg-solana-green/10 text-solana-green border border-solana-green/30'}">
              ${isRebalance ? 'DRIFT: +' + drift + '%' : 'BALANCED (' + drift + '%)'}
            </span>
          </td>

          <!-- 6. Rebalance Action -->
          <td class="py-3 px-3 text-xs font-mono max-w-xs">
            <span class="${isRebalance ? 'text-amber-300 font-bold' : 'text-gray-400'}">
              ${isRebalance ? '⚠️ ' + p.recommended_swap : '✅ In 50/50 Optimal Band'}
            </span>
          </td>

          <!-- 7. Alpha / Vol -->
          <td class="py-3 px-3 font-mono text-xs whitespace-nowrap">
            <div class="font-bold text-solana-green">+${stats.cumulative_harvested_alpha_pct || 0}% Alpha</div>
            <div class="text-[10px] text-gray-400">${stats.total_cycles_completed || 0} cycles • ${stats.annualized_volatility || '-'} σ</div>
          </td>

          <!-- 8. Execution -->
          <td class="py-3 px-3 text-right whitespace-nowrap">
            <div class="flex items-center justify-end gap-1.5">
              <button onclick="triggerSimulateSwap('${tokenA}', '${tokenB}', 1.0)" class="px-2.5 py-1 bg-solana-card hover:bg-solana-border text-amber-400 border border-amber-500/30 rounded text-xs font-bold transition">
                Simulate
              </button>
              <a href="https://jup.ag/swap/${tokenA}-${tokenB}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 bg-solana-purple/20 text-solana-purple hover:bg-solana-purple/30 border border-solana-purple/30 rounded text-xs font-bold transition flex items-center gap-1">
                Trade ↗
              </a>
            </div>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
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
  loadDemoState();
  if (currentTab === 'lst') loadLstDepeg();
  else if (currentTab === 'pairs' || currentTab === 'shannon') {
    loadShannon();
    loadPairsRotation();
  }
  else if (currentTab === 'loops') loadLoops();
}

// =============================================================
// 7. AUTONOMOUS QUANT DEMO BOT (1.0 SOL / MAX 2 SLOTS)
// =============================================================
let demoState = null;

async function loadDemoState() {
  try {
    // If we have saved state in localStorage, sync it first if server is fresh
    const localSaved = localStorage.getItem('solana_demo_state');
    if (localSaved && !demoState) {
      try {
        const parsed = JSON.parse(localSaved);
        await fetch('/api/demo/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state: parsed })
        });
      } catch (e) {}
    }

    const res = await fetch('/api/demo/state');
    demoState = await res.json();
    
    // Save to localStorage for client-side cloud persistence
    if (demoState && demoState.initial_capital_sol) {
      localStorage.setItem('solana_demo_state', JSON.stringify(demoState));
    }

    renderDemoUI(demoState);
  } catch (err) {
    console.error('Error loading demo state:', err);
  }
}

function renderDemoUI(state) {
  if (!state) return;

  // Status & Buttons
  const isRunning = state.is_running;
  const statusBadge = document.getElementById('demo-status-badge');
  const toggleBtn = document.getElementById('btn-demo-toggle');
  const toggleLabel = document.getElementById('demo-toggle-label');
  const pulse = document.getElementById('demo-pulse');

  if (statusBadge) {
    statusBadge.className = isRunning
      ? 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-solana-green/20 text-solana-green border border-solana-green/40'
      : 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-gray-800 text-gray-400 border border-gray-700';
    statusBadge.innerText = isRunning ? 'ACTIVE (LIVE 24/7)' : 'PAUSED';
  }

  if (toggleBtn && toggleLabel) {
    toggleBtn.className = isRunning
      ? 'px-4 py-2.5 rounded-xl font-mono text-xs font-bold transition flex items-center gap-2 shadow-lg bg-amber-500 text-black hover:bg-amber-400'
      : 'px-4 py-2.5 rounded-xl font-mono text-xs font-bold transition flex items-center gap-2 shadow-lg bg-solana-green text-black hover:bg-solana-green/90';
    toggleLabel.innerText = isRunning ? 'Pause Bot' : 'Start Demo';
  }

  if (pulse) {
    pulse.className = isRunning ? 'w-3 h-3 rounded-full bg-solana-green animate-ping' : 'w-3 h-3 rounded-full bg-gray-600';
  }

  // KPIs
  const balEl = document.getElementById('demo-kpi-balance');
  const balUsdEl = document.getElementById('demo-kpi-balance-usd');
  const profitEl = document.getElementById('demo-kpi-profit');
  const profitPctEl = document.getElementById('demo-kpi-profit-pct');
  const activeCountEl = document.getElementById('demo-kpi-active-count');
  const availSolEl = document.getElementById('demo-kpi-available-sol');

  const bal = state.current_balance_sol || 1.0;
  const profit = state.total_profit_sol || 0.0;
  const profitPct = state.total_profit_pct || 0.0;
  const avail = state.available_sol || 1.0;
  const activeCount = state.active_positions ? state.active_positions.length : 0;

  if (balEl) balEl.innerText = bal.toFixed(4);
  if (balUsdEl) balUsdEl.innerText = `≈ $${(bal * 95.0).toFixed(2)} USD`;
  if (profitEl) {
    profitEl.innerText = `${profit >= 0 ? '+' : ''}${profit.toFixed(4)}`;
    profitEl.className = profit >= 0 ? 'text-xl font-bold font-mono text-solana-green mt-1 flex items-baseline gap-1.5' : 'text-xl font-bold font-mono text-red-400 mt-1 flex items-baseline gap-1.5';
  }
  if (profitPctEl) {
    profitPctEl.innerText = `${profitPct >= 0 ? '+' : ''}${profitPct.toFixed(2)}% Net Growth`;
    profitPctEl.className = profitPct >= 0 ? 'text-[11px] text-solana-green/90 font-mono font-bold block mt-0.5' : 'text-[11px] text-red-400/90 font-mono font-bold block mt-0.5';
  }
  if (activeCountEl) activeCountEl.innerText = activeCount;
  if (availSolEl) availSolEl.innerText = `Available: ${avail.toFixed(4)} SOL`;

  // Render 2 Active Slots
  const slotsContainer = document.getElementById('demo-active-slots');
  if (slotsContainer) {
    let slotsHtml = '';
    const active = state.active_positions || [];

    for (let slot = 0; slot < 2; slot++) {
      const pos = active[slot];
      if (pos) {
        const pnl = pos.unrealized_pnl_pct || 0.0;
        const isUp = pnl >= 0;
        slotsHtml += `
          <div class="bg-solana-dark border border-solana-green/40 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between pb-2 border-b border-solana-border/50">
                <div class="flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full bg-solana-green animate-pulse"></span>
                  <span class="font-bold text-white font-mono text-sm">Slot ${slot + 1}: ${pos.pair}</span>
                </div>
                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded ${isUp ? 'bg-solana-green/20 text-solana-green border border-solana-green/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}">
                  ${isUp ? '+' : ''}${pnl.toFixed(2)}% PnL
                </span>
              </div>
              <div class="grid grid-cols-2 gap-2 mt-3 text-xs font-mono">
                <div>
                  <span class="text-gray-400 text-[10px] block">Invested:</span>
                  <span class="font-bold text-white">${pos.sol_invested} SOL</span>
                </div>
                <div>
                  <span class="text-gray-400 text-[10px] block">Tokens Held:</span>
                  <span class="font-bold text-solana-purple">${pos.tokens_held.toLocaleString()} ${pos.base_token}</span>
                </div>
                <div>
                  <span class="text-gray-400 text-[10px] block">Entry Ratio (Z-Score):</span>
                  <span class="text-gray-300">${formatRatio(pos.entry_ratio)} (${pos.entry_z_score}&sigma;)</span>
                </div>
                <div>
                  <span class="text-gray-400 text-[10px] block">Current Ratio:</span>
                  <span class="${isUp ? 'text-solana-green' : 'text-amber-400'} font-bold">${formatRatio(pos.current_ratio)}</span>
                </div>
              </div>
            </div>
            <div class="mt-3 pt-2 border-t border-solana-border/40 flex items-center justify-between text-[11px] font-mono">
              <span class="text-gray-400">Target Reversion: <span class="text-solana-green font-bold">+${pos.target_yield_pct}%</span></span>
              <span class="text-solana-green font-bold">Auto-Take-Profit ON</span>
            </div>
          </div>
        `;
      } else {
        slotsHtml += `
          <div class="bg-solana-dark/50 border border-dashed border-gray-700 rounded-xl p-4 flex flex-col justify-center items-center text-center min-h-[140px]">
            <div class="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-gray-500 mb-2">
              <i data-lucide="plus" class="w-4 h-4"></i>
            </div>
            <span class="font-bold text-gray-400 text-xs font-mono">Slot ${slot + 1}: Idle & Ready</span>
            <p class="text-[11px] text-gray-500 mt-1 font-mono max-w-xs">
              Waiting for extreme oversold trigger (Z &le; -2.0&sigma;) on Solana leaders. Max tranche: 0.45 SOL.
            </p>
          </div>
        `;
      }
    }
    slotsContainer.innerHTML = slotsHtml;
  }

  // Render Trade History
  const tbody = document.getElementById('demo-trades-tbody');
  const countEl = document.getElementById('demo-trades-count');
  const history = state.trade_history || [];

  if (countEl) {
    countEl.innerText = `${history.length} completed trade${history.length === 1 ? '' : 's'}`;
  }

  if (tbody) {
    if (history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-6 text-center text-gray-500 font-mono text-xs">
            No closed trades yet. The engine enters automatically on Z &le; -2.0&sigma; and banks profit on mean reversion.
          </td>
        </tr>
      `;
    } else {
      let tHtml = '';
      history.forEach(t => {
        const dateStr = new Date(t.exit_time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const isWin = t.net_profit_sol >= 0;
        tHtml += `
          <tr class="hover:bg-solana-dark/50 transition">
            <td class="py-2.5 px-3 text-gray-400 whitespace-nowrap">${dateStr}</td>
            <td class="py-2.5 px-3 font-bold text-white whitespace-nowrap">
              <span class="text-solana-green">SWAP</span> ${t.pair}
            </td>
            <td class="py-2.5 px-3 text-gray-300 font-mono">${t.sol_invested} SOL</td>
            <td class="py-2.5 px-3 text-gray-400 font-mono text-[11px]">
              ${formatRatio(t.entry_ratio)} &rarr; <span class="${isWin ? 'text-solana-green font-bold' : 'text-gray-300'}">${formatRatio(t.exit_ratio)}</span>
            </td>
            <td class="py-2.5 px-3 font-bold text-white font-mono">${t.sol_returned} SOL</td>
            <td class="py-2.5 px-3 font-bold font-mono whitespace-nowrap ${isWin ? 'text-solana-green' : 'text-red-400'}">
              ${isWin ? '+' : ''}${t.net_profit_sol} SOL (${isWin ? '+' : ''}${t.net_profit_pct}%)
            </td>
            <td class="py-2.5 px-3 text-right text-gray-400 text-[11px] whitespace-nowrap">
              <span class="px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700">${t.exit_reason || 'Reversion Hit'}</span>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = tHtml;
    }
  }

  if (window.lucide) lucide.createIcons();
}

async function toggleDemoBot() {
  try {
    const res = await fetch('/api/demo/toggle', { method: 'POST' });
    demoState = await res.json();
    if (demoState && demoState.initial_capital_sol) {
      localStorage.setItem('solana_demo_state', JSON.stringify(demoState));
    }
    renderDemoUI(demoState);
  } catch (err) {
    console.error('Error toggling demo bot:', err);
  }
}

async function confirmResetDemo() {
  if (confirm('هل أنت متأكد أنك باغي تمسح الـ Historique وتبدا من اللول بـ 1.0 SOL؟\n\nAre you sure you want to reset and restart fresh with 1.000 SOL?')) {
    try {
      const res = await fetch('/api/demo/reset', { method: 'POST' });
      demoState = await res.json();
      localStorage.removeItem('solana_demo_state');
      localStorage.setItem('solana_demo_state', JSON.stringify(demoState));
      renderDemoUI(demoState);
    } catch (err) {
      console.error('Error resetting demo:', err);
    }
  }
}

async function tickDemoBot() {
  if (demoState && demoState.is_running) {
    try {
      const res = await fetch('/api/demo/tick', { method: 'POST' });
      demoState = await res.json();
      if (demoState && demoState.initial_capital_sol) {
        localStorage.setItem('solana_demo_state', JSON.stringify(demoState));
      }
      renderDemoUI(demoState);
    } catch (e) {}
  }
}

// Initial boot
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  loadTickers();
  loadLstDepeg();
  loadDemoState();
  
  // Real-time live auto-refresh every 2.5 seconds
  setInterval(pollActiveTab, 2500);
  // Auto-tick demo bot every 8 seconds
  setInterval(tickDemoBot, 8000);
});
