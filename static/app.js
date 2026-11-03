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
  if (currentTab === 'lst') loadLstDepeg();
  else if (currentTab === 'pairs' || currentTab === 'shannon') {
    loadShannon();
    loadPairsRotation();
  }
  else if (currentTab === 'loops') loadLoops();
}

// =============================================================
// 7. PURE CLAUDE SHANNON 6-BASKET 50/50 THRESHOLD ENGINE (1.0 SOL)
// =============================================================
const DEMO_STRATEGY_ID = 'shannon_6basket_threshold_v1';
const DEMO_STORAGE_KEY = 'solana_shannon_6basket_state_v1';
const BASKET_ORDER = ['JUP', 'RAY', 'JTO', 'KMNO', 'MET', 'PUMP'];

let demoState = null;
let showAllCrossPairs = false;

function toggleCrossPairsView() {
  showAllCrossPairs = !showAllCrossPairs;
  if (demoState) {
    renderDemoUI(demoState);
  }
}

function buildCrossPairsFromSlots(activeSlots, crossBandPct = 1.10, maxStreak = 2) {
  const syms = BASKET_ORDER.filter(s => activeSlots && activeSlots[s]);
  const list = [];
  for (let i = 0; i < syms.length; i++) {
    for (let j = i + 1; j < syms.length; j++) {
      const s1 = syms[i];
      const s2 = syms[j];
      const d1 = activeSlots[s1].drift_pct || 0.0;
      const d2 = activeSlots[s2].drift_pct || 0.0;
      const highSym = d1 >= d2 ? s1 : s2;
      const lowSym = d1 >= d2 ? s2 : s1;
      const dHigh = d1 >= d2 ? d1 : d2;
      const dLow = d1 >= d2 ? d2 : d1;
      const spread = dHigh - dLow;
      const streak = activeSlots[lowSym].cross_buy_streak || 0;
      const isOpp = dHigh >= 0.45 && dLow <= -0.45;
      const isReady = spread >= crossBandPct;
      const isSafe = streak < maxStreak;
      list.push({
        pair: `${highSym} -> ${lowSym}`,
        high_sym: highSym,
        low_sym: lowSym,
        drift_high_pct: dHigh,
        drift_low_pct: dLow,
        spread_drift_pct: spread,
        rel_price_spread_pct: spread * 4.0,
        streak_low: streak,
        max_streak: maxStreak,
        status: (isOpp && isReady && isSafe)
          ? 'READY_CROSS_SWAP'
          : (isOpp && isReady && !isSafe)
            ? 'BLEED_CAP_HOLD'
            : isOpp
              ? 'WATCHING_SPREAD'
              : 'NEUTRAL'
      });
    }
  }
  list.sort((a, b) => b.spread_drift_pct - a.spread_drift_pct);
  return list;
}

async function loadDemoState() {
  try {
    // Purge legacy Zeno/dip-filter cache if present
    localStorage.removeItem('solana_demo_state');

    const localSaved = localStorage.getItem(DEMO_STORAGE_KEY);
    if (localSaved) {
      try {
        const parsed = JSON.parse(localSaved);
        if (
          parsed &&
          parsed.strategy === DEMO_STRATEGY_ID &&
          parsed.active_slots &&
          Object.keys(parsed.active_slots).length > 0
        ) {
          demoState = parsed;
          renderDemoUI(demoState);
          if (demoState.is_running) {
            tickDemoBot();
          }
          return;
        }
      } catch (e) {
        console.error('Error parsing saved 6-basket state:', e);
      }
    }

    const res = await fetch('/api/demo/state');
    const serverState = await res.json();
    if (serverState && serverState.strategy === DEMO_STRATEGY_ID) {
      demoState = serverState;
      localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(demoState));
      renderDemoUI(demoState);
    }
  } catch (err) {
    console.error('Error loading 6-basket Shannon state:', err);
  }
}

function renderDemoUI(state) {
  if (!state) return;

  const isRunning = Boolean(state.is_running);
  const bandPct = state.rebalance_band_pct || 1.0;
  const solUsd = state.sol_price_usd || 95.5;

  // 1. Top Status & Toggle Button
  const statusBadge = document.getElementById('demo-status-badge');
  const toggleBtn = document.getElementById('btn-demo-toggle');
  const toggleLabel = document.getElementById('demo-toggle-label');
  const pulse = document.getElementById('demo-pulse');
  const gasEl = document.getElementById('demo-gas-reserve');

  if (statusBadge) {
    statusBadge.className = isRunning
      ? 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-solana-green/20 text-solana-green border border-solana-green/40'
      : 'px-3 py-1 rounded-full text-xs font-mono font-bold bg-gray-800 text-gray-400 border border-gray-700';
    statusBadge.innerText = isRunning ? 'ACTIVE (6 BASKETS 50/50 LIVE)' : 'PAUSED';
  }

  if (toggleBtn && toggleLabel) {
    toggleBtn.className = isRunning
      ? 'px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition flex items-center gap-2 shadow-lg bg-amber-500 text-black hover:bg-amber-400'
      : 'px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition flex items-center gap-2 shadow-lg bg-solana-green text-black hover:bg-solana-green/90';
    toggleLabel.innerText = isRunning ? 'Pause Harvester' : 'Start Harvester';
  }

  if (pulse) {
    pulse.className = isRunning
      ? 'w-3 h-3 rounded-full bg-solana-green animate-ping'
      : 'w-3 h-3 rounded-full bg-gray-600';
  }

  const gasReserve = state.gas_reserve_sol !== undefined ? state.gas_reserve_sol : 0.04;
  if (gasEl) {
    gasEl.innerText = `${gasReserve.toFixed(4)} SOL`;
  }
  const crossSwapsEl = document.getElementById('demo-cross-swaps-count');
  if (crossSwapsEl) {
    crossSwapsEl.innerText = state.total_cross_swaps || 0;
  }

  // 2. KPI Cards
  const balEl = document.getElementById('demo-kpi-balance');
  const balUsdEl = document.getElementById('demo-kpi-balance-usd');
  const profitEl = document.getElementById('demo-kpi-profit');
  const profitPctEl = document.getElementById('demo-kpi-profit-pct');
  const slotsEl = document.getElementById('demo-kpi-slots');
  const cyclesEl = document.getElementById('demo-kpi-cycles');
  const surplusEl = document.getElementById('demo-kpi-surplus');
  const liquidSolEl = document.getElementById('demo-kpi-liquid-sol');
  const cashPctEl = document.getElementById('demo-kpi-cash-pct');

  const bal = state.current_balance_sol !== undefined ? state.current_balance_sol : 1.0;
  const profit = state.total_profit_sol || 0.0;
  const profitPct = state.total_profit_pct || 0.0;
  const totalAlpha = state.total_harvested_alpha_sol || 0.0;
  const surplus = state.rebalance_surplus_sol || 0.0;
  const activeSlots = state.active_slots || {};
  const activeCount = Object.keys(activeSlots).length;
  const cycles = state.total_cycles_completed || 0;

  const totalLiquidSol = state.total_liquid_sol !== undefined
    ? state.total_liquid_sol
    : (state.central_cash_sol !== undefined ? state.central_cash_sol : 0.52);
  const totalTokenSol = state.total_token_val_sol !== undefined
    ? state.total_token_val_sol
    : Math.max(0.0, bal - totalLiquidSol);

  const liquidPct = bal > 0 ? (totalLiquidSol / bal) * 100.0 : 52.0;
  const tokenPct = bal > 0 ? (totalTokenSol / bal) * 100.0 : 48.0;

  if (balEl) balEl.innerText = bal.toFixed(4);
  if (balUsdEl) balUsdEl.innerText = `≈ $${(bal * solUsd).toFixed(2)} USD (SOL @ $${solUsd.toFixed(2)})`;

  if (profitEl) {
    profitEl.innerText = `+${totalAlpha.toFixed(5)}`;
    profitEl.className = 'text-xl font-bold font-mono text-solana-green mt-1 flex items-baseline gap-1.5';
  }
  if (profitPctEl) {
    const sign = profit >= 0 ? '+' : '';
    profitPctEl.innerText = `Portfolio PnL: ${sign}${profit.toFixed(4)} SOL (${sign}${profitPct.toFixed(2)}%)`;
    profitPctEl.className = profit >= 0
      ? 'text-[11px] text-solana-green/90 font-mono font-bold block mt-0.5'
      : 'text-[11px] text-gray-300 font-mono block mt-0.5';
  }

  if (slotsEl) slotsEl.innerText = `${activeCount} / 6`;
  if (cyclesEl) cyclesEl.innerText = cycles;
  if (surplusEl) {
    const sSign = surplus >= 0 ? '+' : '';
    surplusEl.innerText = `vs Static 50/50: ${sSign}${surplus.toFixed(5)} SOL`;
    surplusEl.className = surplus >= 0
      ? 'text-[11px] text-solana-green font-mono block mt-0.5'
      : 'text-[11px] text-amber-300 font-mono block mt-0.5';
  }

  if (liquidSolEl) liquidSolEl.innerText = totalLiquidSol.toFixed(4);
  if (cashPctEl) {
    cashPctEl.innerText = `${liquidPct.toFixed(1)}% SOL Cash / ${tokenPct.toFixed(1)}% Tokens`;
  }

  // 3. Multi-Basket Capital Allocation Bar (Gas + 6 Baskets)
  const allocContainer = document.getElementById('allocation-bar-container');
  const allocLegend = document.getElementById('allocation-legend');
  if (allocContainer && allocLegend) {
    const BASKET_COLORS = {
      JUP: { bg: 'bg-solana-green', text: 'text-solana-green' },
      RAY: { bg: 'bg-solana-purple', text: 'text-solana-purple' },
      JTO: { bg: 'bg-blue-500', text: 'text-blue-400' },
      KMNO: { bg: 'bg-cyan-400', text: 'text-cyan-300' },
      MET: { bg: 'bg-amber-400', text: 'text-amber-300' },
      PUMP: { bg: 'bg-pink-500', text: 'text-pink-400' }
    };

    const unalloc = state.unallocated_cash_sol || 0.0;
    const reservePool = gasReserve + unalloc;
    const reservePct = bal > 0 ? (reservePool / bal) * 100.0 : 4.0;

    let barsHtml = `<div class="bg-gray-500 h-3.5 transition-all duration-500" style="width: ${reservePct.toFixed(2)}%" title="Gas Reserve: ${reservePool.toFixed(4)} SOL"></div>`;
    let legendHtml = `<span class="flex items-center gap-1 text-gray-300"><span class="w-2 h-2 rounded-full bg-gray-400"></span> Gas: ${reservePool.toFixed(3)} SOL</span>`;

    BASKET_ORDER.forEach(sym => {
      const slot = activeSlots[sym];
      if (!slot) return;
      const slotVal = slot.slot_equity || 0.0;
      const slotPct = bal > 0 ? (slotVal / bal) * 100.0 : 0.0;
      const c = BASKET_COLORS[sym] || { bg: 'bg-solana-purple', text: 'text-solana-purple' };
      barsHtml += `<div class="${c.bg} h-3.5 transition-all duration-500 border-l border-solana-dark/60" style="width: ${slotPct.toFixed(2)}%" title="${sym} 50/50 Basket: ${slotVal.toFixed(4)} SOL"></div>`;
      legendHtml += `<span class="flex items-center gap-1 ${c.text}"><span class="w-2 h-2 rounded-full ${c.bg}"></span> ${sym}: ${slotVal.toFixed(3)}</span>`;
    });

    allocContainer.innerHTML = barsHtml;
    allocLegend.innerHTML = legendHtml;
  }

  // 4. 6 Active 50/50 Baskets Grid (3x2 Scale Cards)
  const gridEl = document.getElementById('active-positions-grid');
  const slotsInd = document.getElementById('active-slots-indicator');
  if (slotsInd) {
    slotsInd.innerText = `${activeCount} / 6 Baskets Active (±${bandPct}% SOL Band + 15 Cross-Pairs)`;
  }

  if (gridEl) {
    const presentKeys = BASKET_ORDER.filter(sym => activeSlots[sym]);
    if (presentKeys.length === 0) {
      gridEl.innerHTML = `
        <div class="col-span-3 py-6 text-center text-gray-400 font-mono text-xs bg-solana-dark/40 border border-solana-border/50 rounded-xl">
          Initializing 6 Pure Shannon 50/50 Baskets (JUP, RAY, JTO, KMNO, MET, PUMP) from live Jupiter feeds...
        </div>
      `;
    } else {
      let cardsHtml = '';
      presentKeys.forEach(sym => {
        const slot = activeSlots[sym];
        const wCash = slot.weight_cash_pct !== undefined ? slot.weight_cash_pct : 50.0;
        const wToken = slot.weight_token_pct !== undefined ? slot.weight_token_pct : 50.0;
        const drift = slot.drift_pct !== undefined ? slot.drift_pct : 0.0;
        const absDrift = Math.abs(drift);
        const isTrigger = absDrift >= bandPct;
        const isNear = absDrift >= bandPct * 0.75;

        const slotEquity = slot.slot_equity || 0.16;
        const cashVal = slot.slot_cash !== undefined ? slot.slot_cash : 0.08;
        const tokenVal = slot.token_sol_val !== undefined ? slot.token_sol_val : 0.08;
        const tokensHeld = slot.tokens_held || 0.0;
        const livePrice = slot.current_ratio || 0.0;
        const priceChg = slot.price_change_from_ref_pct || 0.0;
        const alpha = slot.harvested_alpha_sol || 0.0;
        const slotCycles = slot.cycles_completed || 0;
        const crossStreak = slot.cross_buy_streak || 0;

        let driftBadgeClass = 'bg-solana-green/15 text-solana-green border-solana-green/30';
        let driftLabel = `Drift: ${drift >= 0 ? '+' : ''}${drift.toFixed(2)}%`;
        if (isTrigger) {
          driftBadgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/50 animate-pulse';
          driftLabel = `⚡ REBALANCE (${drift >= 0 ? '+' : ''}${drift.toFixed(2)}%)`;
        } else if (isNear) {
          driftBadgeClass = 'bg-amber-500/15 text-amber-300 border-amber-500/30';
        }

        cardsHtml += `
          <div class="bg-solana-dark/90 border ${isTrigger ? 'border-amber-500/60 shadow-lg shadow-amber-500/10' : 'border-solana-border hover:border-solana-green/50'} transition rounded-xl p-4 flex flex-col justify-between font-mono">
            <!-- Header -->
            <div class="flex items-center justify-between border-b border-solana-border/40 pb-2">
              <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full ${isTrigger ? 'bg-amber-400 animate-ping' : 'bg-solana-green'}"></span>
                <span class="font-bold text-white text-sm">SOL / ${sym}</span>
              </div>
              <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${driftBadgeClass}">
                ${driftLabel}
              </span>
            </div>

            <!-- 50/50 Value Scale Bar (الميزان) -->
            <div class="my-3">
              <div class="flex justify-between text-[10px] mb-1">
                <span class="text-solana-green font-bold">SOL: ${wCash.toFixed(1)}%</span>
                <span class="text-gray-400">Scale 50 / 50</span>
                <span class="text-solana-purple font-bold">${sym}: ${wToken.toFixed(1)}%</span>
              </div>
              <div class="relative w-full bg-gray-800 rounded-full h-2.5 flex overflow-hidden border border-solana-border/60">
                <div class="bg-solana-green h-2.5 transition-all duration-500" style="width: ${wCash}%"></div>
                <div class="bg-solana-purple h-2.5 transition-all duration-500" style="width: ${wToken}%"></div>
                <div class="absolute top-0 bottom-0 left-1/2 w-0.5 bg-white/80 -translate-x-1/2" title="Exact 50/50 Center"></div>
              </div>
            </div>

            <!-- Two Kaffas & Price Details -->
            <div class="grid grid-cols-2 gap-2 my-1 text-[11px] bg-solana-card/40 p-2.5 rounded-lg border border-solana-border/30">
              <div>
                <span class="text-gray-400 block text-[10px]">SOL Cash Kaffa:</span>
                <span class="text-solana-green font-bold">${cashVal.toFixed(4)} SOL</span>
              </div>
              <div>
                <span class="text-gray-400 block text-[10px]">${sym} Value Kaffa:</span>
                <span class="text-solana-purple font-bold">${tokenVal.toFixed(4)} SOL</span>
              </div>
              <div>
                <span class="text-gray-400 block text-[10px]">Live Price (Δ Ref):</span>
                <span class="text-white font-bold">${formatRatio(livePrice)} <span class="${priceChg >= 0 ? 'text-solana-green' : 'text-amber-300'} text-[10px]">(${priceChg >= 0 ? '+' : ''}${priceChg.toFixed(1)}%)</span></span>
              </div>
              <div>
                <span class="text-gray-400 block text-[10px]">${sym} Qty Held:</span>
                <span class="text-gray-200 font-bold">${tokensHeld.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
              </div>
            </div>

            <!-- Footer -->
            <div class="pt-2 border-t border-solana-border/40 flex items-center justify-between text-[10px] text-gray-400 mt-2">
              <span>Equity: <strong class="text-white">${slotEquity.toFixed(4)} SOL</strong></span>
              <span>Cycles: <strong class="text-amber-300">${slotCycles}</strong> | Streak: <strong class="text-cyan-300">${crossStreak}/2</strong> | Alpha: <strong class="text-solana-green">+${alpha.toFixed(5)}</strong></span>
            </div>
          </div>
        `;
      });
      gridEl.innerHTML = cardsHtml;
    }
  }

  // 5. Live 6-Basket Threshold Drift Monitor Table
  const radarTbody = document.getElementById('scanner-radar-tbody');
  const scanned = state.scanned_pairs_status || [];
  if (radarTbody && scanned.length > 0) {
    let rHtml = '';
    scanned.forEach(item => {
      const pChg = item.price_change_ref_pct || 0.0;
      const drift = item.drift_pct || 0.0;
      const prog = item.progress_to_trigger_pct || 0.0;
      const wCash = item.weight_cash_pct !== undefined ? item.weight_cash_pct : 50.0;
      const wTok = item.weight_token_pct !== undefined ? item.weight_token_pct : 50.0;

      let badgeHtml = '';
      if (item.gate_status === 'CROSS_ROTATED') {
        badgeHtml = '<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 text-[10px] font-bold">🔄 CROSS-ROTATED 50/50</span>';
      } else if (item.gate_status === 'REBALANCED_50_50') {
        badgeHtml = '<span class="px-2 py-0.5 rounded bg-solana-green/20 text-solana-green border border-solana-green/40 text-[10px] font-bold">⚡ REBALANCED 50/50</span>';
      } else if (item.gate_status === 'NEAR_TRIGGER') {
        badgeHtml = `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px] font-bold animate-pulse">⚠️ NEAR ±${bandPct.toFixed(1)}% BAND</span>`;
      } else if (item.gate_status === 'BLOCKED_FEE_DRAG') {
        badgeHtml = '<span class="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 text-[10px]">🛡️ FEE GATE HOLD</span>';
      } else if (item.gate_status === 'IN_OPTIMAL_BAND') {
        badgeHtml = '<span class="px-2 py-0.5 rounded bg-solana-purple/20 text-solana-purple border border-solana-purple/40 text-[10px]">✅ IN 50/50 BAND</span>';
      } else {
        badgeHtml = '<span class="px-2 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700 text-[10px]">AWAITING FEED</span>';
      }

      rHtml += `
        <tr class="hover:bg-solana-dark/50 transition">
          <td class="py-2 px-3 font-bold text-white">${item.pair}</td>
          <td class="py-2 px-3 text-gray-400">${formatRatio(item.last_rebal_ratio || item.entry_ratio)}</td>
          <td class="py-2 px-3 text-white font-bold">${formatRatio(item.current_ratio)}</td>
          <td class="py-2 px-3 font-bold ${pChg >= 0 ? 'text-solana-green' : 'text-amber-300'}">${pChg >= 0 ? '+' : ''}${pChg.toFixed(2)}%</td>
          <td class="py-2 px-3 text-gray-300">${wCash.toFixed(1)}% / ${wTok.toFixed(1)}%</td>
          <td class="py-2 px-3">
            <div class="flex items-center gap-2">
              <span class="font-bold ${Math.abs(drift) >= bandPct * 0.75 ? 'text-amber-300' : 'text-gray-200'}">${drift >= 0 ? '+' : ''}${drift.toFixed(2)}%</span>
              <div class="w-16 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                <div class="${prog >= 75 ? 'bg-amber-400' : 'bg-solana-green'} h-1.5" style="width: ${prog}%"></div>
              </div>
            </div>
          </td>
          <td class="py-2 px-3 text-right">${badgeHtml}</td>
        </tr>
      `;
    });
    radarTbody.innerHTML = rHtml;
  }

  // 5.25 15 Cross-Token Pairs Triangular Rotation Matrix Table
  const crossTbody = document.getElementById('cross-pairs-radar-tbody');
  const crossCountBadge = document.getElementById('cross-pairs-count-badge');
  const crossBtnLabel = document.getElementById('btn-toggle-cross-pairs-label');
  const crossBandPct = state.cross_spread_band_pct || 1.10;
  const maxStreakVal = state.max_cross_buy_streak || 2;

  let allCrossPairs = (state.cross_pairs_status && state.cross_pairs_status.length >= 15)
    ? state.cross_pairs_status
    : buildCrossPairsFromSlots(activeSlots, crossBandPct, maxStreakVal);

  const visibleCrossPairs = showAllCrossPairs ? allCrossPairs : allCrossPairs.slice(0, 6);

  if (crossCountBadge) {
    crossCountBadge.innerText = showAllCrossPairs
      ? `Showing All ${allCrossPairs.length} / 15 Pairs`
      : `Showing Top ${visibleCrossPairs.length} / 15 Pairs`;
  }
  if (crossBtnLabel) {
    crossBtnLabel.innerText = showAllCrossPairs
      ? '🔼 Show Top 6 Only (عرض أفضل 6)'
      : '👁️ Show All 15 Pairs (عرض الكل)';
  }

  if (crossTbody) {
    if (visibleCrossPairs.length === 0) {
      crossTbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-3 text-center text-gray-500 font-mono text-xs">
            Scanning 15 cross-token pairs (JUP, RAY, JTO, KMNO, MET, PUMP) for relative scale divergence...
          </td>
        </tr>
      `;
    } else {
      let cHtml = '';
      visibleCrossPairs.forEach((cp, idx) => {
        const dHigh = cp.drift_high_pct || 0.0;
        const dLow = cp.drift_low_pct || 0.0;
        const spread = cp.spread_drift_pct || 0.0;
        const relPrice = cp.rel_price_spread_pct || 0.0;
        const streak = cp.streak_low || 0;
        const maxStreak = cp.max_streak || 2;
        const prog = Math.min(100.0, (spread / crossBandPct) * 100.0);

        let statusBadge = '';
        if (cp.status === 'EXECUTED_CROSS_SWAP') {
          statusBadge = '<span class="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 text-[10px] font-bold">🔄 CROSS-SWAP EXECUTED</span>';
        } else if (cp.status === 'READY_CROSS_SWAP') {
          statusBadge = '<span class="px-2 py-0.5 rounded bg-solana-green/20 text-solana-green border border-solana-green/50 text-[10px] font-bold animate-pulse">⚡ READY CROSS-SWAP</span>';
        } else if (cp.status === 'BLEED_CAP_HOLD') {
          statusBadge = `<span class="px-2 py-0.5 rounded bg-red-500/20 text-red-300 border border-red-500/40 text-[10px]">🛡️ BLEED CAP (${streak}/${maxStreak})</span>`;
        } else if (cp.status === 'WATCHING_SPREAD') {
          statusBadge = '<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[10px]">👀 OPPOSITE TILT</span>';
        } else {
          statusBadge = '<span class="px-2 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700 text-[10px]">⚖️ CO-MOVING</span>';
        }

        cHtml += `
          <tr class="hover:bg-solana-dark/50 transition">
            <td class="py-2 px-3 font-bold text-cyan-300"><span class="text-gray-500 text-[10px] mr-1">#${idx + 1}</span>${cp.high_sym} &#10140; ${cp.low_sym}</td>
            <td class="py-2 px-3 font-bold ${dHigh >= 0.45 ? 'text-solana-green' : 'text-gray-300'}">${dHigh >= 0 ? '+' : ''}${dHigh.toFixed(2)}% (${cp.high_sym})</td>
            <td class="py-2 px-3 font-bold ${dLow <= -0.45 ? 'text-amber-300' : 'text-gray-300'}">${dLow >= 0 ? '+' : ''}${dLow.toFixed(2)}% (${cp.low_sym})</td>
            <td class="py-2 px-3">
              <div class="flex items-center gap-2">
                <span class="font-bold ${spread >= crossBandPct ? 'text-cyan-300' : 'text-gray-200'}">+${spread.toFixed(2)}%</span>
                <div class="w-16 bg-gray-800 rounded-full h-1.5 overflow-hidden">
                  <div class="${prog >= 100 ? 'bg-cyan-400' : prog >= 70 ? 'bg-amber-400' : 'bg-solana-purple'} h-1.5" style="width: ${prog}%"></div>
                </div>
              </div>
            </td>
            <td class="py-2 px-3 text-white font-bold">+${relPrice.toFixed(2)}%</td>
            <td class="py-2 px-3 ${streak >= maxStreak ? 'text-red-400 font-bold' : 'text-gray-300'}">${streak} / ${maxStreak}</td>
            <td class="py-2 px-3 text-right">${statusBadge}</td>
          </tr>
        `;
      });
      crossTbody.innerHTML = cHtml;
    }
  }

  // 5.5 Coin Quantity Accumulation Mini-Charts (Total Basket SOL + 6 Tokens)
  const qtyChartsGrid = document.getElementById('coin-qty-charts-grid');
  if (qtyChartsGrid) {
    qtyChartsGrid.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3';

    const initBasketSol = state.initial_basket_cash_sol !== undefined ? state.initial_basket_cash_sol : 0.48;
    const currBasketSol = state.total_basket_cash_sol !== undefined ? state.total_basket_cash_sol : 0.48;
    const solDelta = state.basket_sol_delta !== undefined ? state.basket_sol_delta : (currBasketSol - initBasketSol);
    const solDeltaPct = state.basket_sol_delta_pct !== undefined
      ? state.basket_sol_delta_pct
      : (initBasketSol > 0 ? (solDelta / initBasketSol) * 100.0 : 0.0);
    const solHist = (state.sol_qty_history && state.sol_qty_history.length >= 2)
      ? state.sol_qty_history
      : [initBasketSol, currBasketSol];

    const solSpark = generateCoinQtySparkline(solHist, initBasketSol, 'TOTAL_SOL', 480, 60);
    const solIsUp = solDelta > 1e-6;
    const solIsDown = solDelta < -1e-6;
    const solBadgeClass = solIsUp
      ? 'bg-solana-green/20 text-solana-green border-solana-green/40'
      : solIsDown
        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
        : 'bg-gray-800 text-gray-300 border-gray-700';
    const solSign = solDelta >= 0 ? '+' : '';

    let qtyHtml = `
      <!-- Featured Full-Width Card: Total SOL Across All 6 Baskets -->
      <div class="col-span-1 md:col-span-2 lg:col-span-3 bg-gradient-to-r from-solana-dark via-solana-card to-solana-dark border border-solana-green/40 rounded-xl p-4 font-mono">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-3 border-b border-solana-border/50">
          <div class="flex items-center gap-2.5">
            <span class="w-2.5 h-2.5 rounded-full bg-solana-green animate-pulse"></span>
            <div>
              <span class="text-sm font-bold text-white">☀️ TOTAL SOL IN ALL 6 BASKETS (مجموع الـ SOL فـ السلات الستة)</span>
              <span class="block text-[10px] text-gray-400">Sum of SOL Cash Kaffas across JUP, RAY, JTO, KMNO, MET &amp; PUMP (+ ${gasReserve.toFixed(4)} SOL Gas = ${totalLiquidSol.toFixed(4)} SOL Total Wallet)</span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="px-2.5 py-1 rounded-lg text-xs font-bold border ${solBadgeClass}">
              ${solSign}${solDelta.toFixed(5)} SOL (${solSign}${solDeltaPct.toFixed(2)}%)
            </span>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-center mt-3">
          <div class="grid grid-cols-3 md:grid-cols-1 gap-2 text-xs bg-solana-dark/70 p-3 rounded-lg border border-solana-border/40">
            <div>
              <span class="text-gray-400 text-[10px] block">Initial Baskets SOL:</span>
              <span class="text-gray-200 font-bold">${initBasketSol.toFixed(4)} SOL</span>
            </div>
            <div>
              <span class="text-gray-400 text-[10px] block">Current Baskets SOL:</span>
              <span class="text-solana-green font-bold text-sm">${currBasketSol.toFixed(5)} SOL</span>
            </div>
            <div>
              <span class="text-gray-400 text-[10px] block">Net SOL Added / Used:</span>
              <span class="${solIsUp ? 'text-solana-green' : solIsDown ? 'text-amber-300' : 'text-gray-300'} font-bold">${solSign}${solDelta.toFixed(5)} SOL</span>
            </div>
          </div>
          <div class="md:col-span-3 h-16 bg-solana-dark/50 rounded-lg p-2 border border-solana-border/30 flex flex-col justify-between">
            <div class="flex justify-between text-[10px] text-gray-400 px-1">
              <span>Entry Baseline: ${initBasketSol.toFixed(4)} SOL (dashed)</span>
              <span class="text-solana-green font-bold">Live: ${currBasketSol.toFixed(5)} SOL</span>
            </div>
            <div class="w-full h-10">
              ${solSpark}
            </div>
          </div>
        </div>
      </div>
    `;

    // 6 Individual Token Coin Quantity Mini-Chart Cards
    BASKET_ORDER.forEach(sym => {
      const slot = activeSlots[sym];
      if (!slot) return;

      const initTok = slot.initial_tokens !== undefined ? slot.initial_tokens : (slot.tokens_held || 0.0);
      const currTok = slot.tokens_held !== undefined ? slot.tokens_held : 0.0;
      const dTok = slot.token_qty_delta !== undefined ? slot.token_qty_delta : (currTok - initTok);
      const dTokPct = slot.token_qty_delta_pct !== undefined
        ? slot.token_qty_delta_pct
        : (initTok > 0 ? (dTok / initTok) * 100.0 : 0.0);
      const qHist = (slot.qty_history && slot.qty_history.length >= 2)
        ? slot.qty_history
        : [initTok, currTok];

      const isUp = dTok > 1e-5;
      const isDown = dTok < -1e-5;
      const badgeClass = isUp
        ? 'bg-solana-green/20 text-solana-green border-solana-green/40'
        : isDown
          ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
          : 'bg-gray-800 text-gray-400 border-gray-700';
      const sign = dTok >= 0 ? '+' : '';
      const decimals = currTok >= 100 ? 2 : currTok >= 1 ? 3 : 4;

      const sparkSvg = generateCoinQtySparkline(qHist, initTok, sym, 240, 48);

      qtyHtml += `
        <div class="bg-solana-dark/90 border border-solana-border hover:border-solana-purple/50 transition rounded-xl p-3.5 flex flex-col justify-between font-mono">
          <div class="flex items-center justify-between border-b border-solana-border/40 pb-2">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full ${isUp ? 'bg-solana-green' : isDown ? 'bg-amber-400' : 'bg-solana-purple'}"></span>
              <span class="font-bold text-white text-xs">${sym} Coins Held</span>
            </div>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeClass}">
              ${sign}${dTok.toLocaleString(undefined, { maximumFractionDigits: decimals })} ${sym} (${sign}${dTokPct.toFixed(2)}%)
            </span>
          </div>

          <!-- Mini-Chart -->
          <div class="my-2.5 bg-solana-card/50 rounded-lg p-2 border border-solana-border/30">
            <div class="flex justify-between text-[9px] text-gray-400 mb-1">
              <span>Init: ${initTok.toLocaleString(undefined, { maximumFractionDigits: decimals })}</span>
              <span class="${isUp ? 'text-solana-green' : isDown ? 'text-amber-300' : 'text-gray-300'} font-bold">
                ${isUp ? '▲ Accumulated' : isDown ? '▼ Trimmed High' : '● Steady 50/50'}
              </span>
            </div>
            <div class="w-full h-11">
              ${sparkSvg}
            </div>
          </div>

          <!-- Coin Numbers Row -->
          <div class="grid grid-cols-3 gap-1.5 text-[10px] bg-solana-card/30 p-2 rounded-lg border border-solana-border/20">
            <div>
              <span class="text-gray-500 block text-[9px]">Initial Qty</span>
              <span class="text-gray-300 font-bold">${initTok.toLocaleString(undefined, { maximumFractionDigits: decimals })}</span>
            </div>
            <div>
              <span class="text-gray-500 block text-[9px]">Current Qty</span>
              <span class="text-white font-bold">${currTok.toLocaleString(undefined, { maximumFractionDigits: decimals })}</span>
            </div>
            <div class="text-right">
              <span class="text-gray-500 block text-[9px]">Net Δ Coins</span>
              <span class="${isUp ? 'text-solana-green' : isDown ? 'text-amber-300' : 'text-gray-400'} font-bold">${sign}${dTok.toLocaleString(undefined, { maximumFractionDigits: decimals })}</span>
            </div>
          </div>
        </div>
      `;
    });

    qtyChartsGrid.innerHTML = qtyHtml;
  }

  // 6. Execution Ledger
  const tbody = document.getElementById('demo-trades-tbody');
  const countEl = document.getElementById('demo-trades-count');
  const history = state.trade_history || [];

  if (countEl) {
    countEl.innerText = `${history.length} event${history.length === 1 ? '' : 's'}`;
  }

  if (tbody) {
    if (history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="py-6 text-center text-gray-500 font-mono text-xs">
            6-Basket 50/50 + 15 Cross-Pair Harvester ready. Monitoring live price drifts...
          </td>
        </tr>
      `;
    } else {
      let tHtml = '';
      history.forEach(t => {
        const dateStr = new Date(t.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const isPositive = (t.net_profit_sol || 0) >= 0;

        let typeBadge = '';
        if (t.type === 'SHANNON_CROSS_SWAP') {
          typeBadge = '<span class="text-cyan-400 font-bold">🔄 CROSS SWAP</span>';
        } else if (t.type === 'SHANNON_SELL_EXCESS') {
          typeBadge = '<span class="text-solana-green font-bold">⚡ REBALANCE SELL</span>';
        } else if (t.type === 'SHANNON_BUY_DIP') {
          typeBadge = '<span class="text-amber-400 font-bold">🛒 REBALANCE BUY</span>';
        } else if (t.type === 'SHANNON_50_50_INIT') {
          typeBadge = '<span class="text-solana-purple font-bold">🎯 50/50 BASKET</span>';
        } else {
          typeBadge = '<span class="text-gray-300 font-bold">⚖️ SHANNON</span>';
        }

        tHtml += `
          <tr class="hover:bg-solana-dark/50 transition font-mono">
            <td class="py-2.5 px-3 text-gray-400 whitespace-nowrap text-[11px]">${dateStr}</td>
            <td class="py-2.5 px-3 font-bold text-white whitespace-nowrap text-xs">
              ${typeBadge} <span class="text-gray-300 font-normal text-[11px]">${t.action || ''}</span>
            </td>
            <td class="py-2.5 px-3 text-gray-300 text-xs">${t.tranche_sol ? t.tranche_sol.toFixed(4) : '-'} SOL</td>
            <td class="py-2.5 px-3 text-solana-purple font-bold text-xs">${t.tokens_traded ? t.tokens_traded.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-'}</td>
            <td class="py-2.5 px-3 text-gray-400 text-[11px]">${formatRatio(t.ratio || 0)}</td>
            <td class="py-2.5 px-3 font-bold text-xs whitespace-nowrap ${isPositive ? 'text-solana-green' : 'text-gray-400'}">
              ${t.net_profit_sol !== undefined ? (t.net_profit_sol >= 0 ? '+' : '') + t.net_profit_sol.toFixed(5) + ' SOL' : '-'}
            </td>
            <td class="py-2.5 px-3 text-right text-gray-400 text-[11px] whitespace-nowrap">
              <span class="px-2 py-0.5 rounded bg-gray-800/80 text-gray-300 border border-gray-700/60">${t.reason || 'Threshold Drift Rebalance'}</span>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = tHtml;
    }
  }

  if (window.lucide) lucide.createIcons();
}

function generateCoinQtySparkline(data, baselineQty, sym, width = 240, height = 48) {
  const pts = (data && data.length >= 2) ? data : [baselineQty || 1, baselineQty || 1];
  const base = baselineQty !== undefined ? baselineQty : pts[0];

  const allVals = [...pts, base];
  let minVal = Math.min(...allVals);
  let maxVal = Math.max(...allVals);

  if (Math.abs(maxVal - minVal) < 1e-7) {
    const pad = Math.max(Math.abs(base) * 0.02, 0.0005);
    minVal = base - pad;
    maxVal = base + pad;
  } else {
    const pad = (maxVal - minVal) * 0.15;
    minVal -= pad;
    maxVal += pad;
  }

  const range = (maxVal - minVal) || 1;
  const padY = 4;
  const usableH = height - (padY * 2);

  const coords = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * width;
    const y = height - padY - ((v - minVal) / range) * usableH;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const baseY = (height - padY - ((base - minVal) / range) * usableH).toFixed(1);
  const pathD = `M ${coords.join(' L ')}`;
  const areaD = `M ${coords[0]} L ${coords.join(' L ')} L ${width},${height} L 0,${height} Z`;

  const lastVal = pts[pts.length - 1];
  const diff = lastVal - base;
  const strokeColor = diff > 1e-6 ? '#14F195' : diff < -1e-6 ? '#F59E0B' : '#9945FF';
  const gradId = `qty_grad_${sym.replace(/[^a-zA-Z0-9]/g, '_')}`;

  const lastPt = coords[coords.length - 1].split(',');

  return `
    <svg viewBox="0 0 ${width} ${height}" class="w-full h-full overflow-visible" preserveAspectRatio="none">
      <defs>
        <linearGradient id="${gradId}" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.32"/>
          <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <line x1="0" y1="${baseY}" x2="${width}" y2="${baseY}" stroke="#6B7280" stroke-dasharray="3,3" stroke-width="1"/>
      <path d="${areaD}" fill="url(#${gradId})"/>
      <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="${lastPt[0]}" cy="${lastPt[1]}" r="3" fill="${strokeColor}"/>
    </svg>
  `;
}

async function toggleDemoBot() {
  try {
    const nextRunning = demoState ? !demoState.is_running : true;
    if (demoState) {
      demoState.is_running = nextRunning;
      demoState.last_tick_time = Date.now() / 1000;
      localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(demoState));
      renderDemoUI(demoState);
    }

    const res = await fetch('/api/demo/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: demoState, running: nextRunning })
    });
    const updated = await res.json();
    if (updated && updated.strategy === DEMO_STRATEGY_ID) {
      demoState = updated;
      localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(demoState));
      renderDemoUI(demoState);
    }
  } catch (err) {
    console.error('Error toggling 6-basket Shannon bot:', err);
  }
}

async function confirmResetDemo() {
  if (confirm('هل أنت متأكد أنك باغي تعاود تبدا من الزيرو بـ 1.0 SOL مقسمة 50/50 على الـ 6 سلات كاملين؟\n\nReset & deploy fresh 1.0000 SOL across all 6 Shannon 50/50 Baskets?')) {
    try {
      localStorage.removeItem(DEMO_STORAGE_KEY);
      const res = await fetch('/api/demo/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const updated = await res.json();
      if (updated && updated.strategy === DEMO_STRATEGY_ID) {
        demoState = updated;
        localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(demoState));
        renderDemoUI(demoState);
      }
    } catch (err) {
      console.error('Error resetting 6-basket demo:', err);
    }
  }
}

async function tickDemoBot() {
  if (demoState && demoState.is_running) {
    try {
      const res = await fetch('/api/demo/tick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: demoState })
      });
      const updated = await res.json();
      if (updated && updated.strategy === DEMO_STRATEGY_ID) {
        demoState = updated;
        localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(demoState));
        renderDemoUI(demoState);
      }
    } catch (e) {
      console.error('Error ticking 6-basket demo bot:', e);
    }
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
  // Auto-tick 6-basket Shannon bot every 5 seconds
  setInterval(tickDemoBot, 5000);
});
