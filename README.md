# Solana Quant Swap Terminal ⚡

High-Performance Institutional Quantitative Swap Terminal built for the Solana ecosystem, connected in real-time to the official **Jupiter Aggregator (v3 & v1)** APIs (`api.jup.ag`).

![Solana Quant Terminal](shannon_matrix_preview.png)

## 🚀 Overview

The terminal powers 4 specialized quantitative engines designed to extract deterministic alpha and exploit structural micro-inefficiencies across Solana liquidity pools:

1. **Liquid Staking Token (LST) Depeg Arbitrage Terminal**:
   - Monitors physical on-chain reserve backing ratios vs live market spot prices across `JitoSOL`, `mSOL`, and `bSOL`.
   - Real-time depeg alert triggers and instant redemption capture.

2. **Statistical Pairs Swap Rotation Engine (Coin-to-Coin Mean Reversion)**:
   - Direct asset-to-asset coin rotation on top Solana leaders (`JUP`, `RAY`, `JTO`, `KMNO`, `MET`, `PUMP`).
   - Calibrated against Ornstein-Uhlenbeck (OU) process with rolling Z-score divergence ($Z \ge \pm 2.0\sigma$) to accumulate $+1.5\%$ to $+4.5\%$ extra tokens per cycle without fiat exposure.

3. **Multi-Hop Circular Route Swapper (Triangular Arbitrage)**:
   - Scans 3-hop closed routing loops through Jupiter's multi-DEX graph (`SOL -> A -> B -> SOL`).
   - Atomic Jito-bundle compatible execution with sub-2ms route inspection.

4. **Shannon's Demon 50/50 Volatility Harvester Matrix (All 7 Pairs Live)**:
   - Simultaneous 50/50 portfolio rebalancing across all Solana leaders.
   - Deterministic volatility compounding formula ($g = \frac{1}{2}\mu + \frac{1}{8}\sigma^2$) with automated drift alerts and 1-click execution on Jupiter DEX.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python), NumPy, Pydantic, Uvicorn
- **Frontend**: Vanilla JavaScript (ES6+), TailwindCSS, Lucide Icons, Chart.js
- **Routing Engine**: Jupiter Swap API (`api.jup.ag/swap/v1/quote`) & Price API v3
- **Deployment**: Vercel Serverless Functions + Global Edge CDN

---

## 💻 Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/elyousfired/solana-quant-swap-terminal.git
   cd solana-quant-swap-terminal
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the local development server**:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8090 --reload
   ```

4. **Open in browser**:
   Navigate to [http://127.0.0.1:8090](http://127.0.0.1:8090).

---

## 🌐 Cloud Deployment (Vercel)

The repository is configured for zero-config Vercel Serverless deployment:
- Serverless entrypoint in `api/index.py`
- Static edge assets in `public/`
- API routing in `vercel.json`

Deploy instantly:
```bash
vercel --prod
```

---

## 📄 License

MIT License. Designed and built for Solana quantitative research and algorithmic DeFi routing.
