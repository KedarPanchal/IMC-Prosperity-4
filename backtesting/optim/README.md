# Round 3 Backtest Pipeline — IMC Prosperity 4

A self-contained backtesting and parameter-optimisation suite for the Round 3
products: `HYDROGEL_PACK`, `VELVETFRUIT_EXTRACT`, and the 10
`VELVETFRUIT_EXTRACT_VOUCHER` (VEV) call-option contracts.

---

## Directory layout

```
.
├── r3.py               ← your trading algo (submitted to IMC)
├── simulator.py        ← tick-by-tick backtest engine
├── grid.py             ← 225-point grid search → /tmp/grid_results.json
├── centroid.py         ← DBSCAN plateau analysis → best params
├── apply_centroid.py   ← patches r3.py constants + final sanity check
└── round3_data/        ← CSV data folder (see Setup)
    ├── prices_round_3_day_0.csv
    ├── prices_round_3_day_1.csv
    ├── prices_round_3_day_2.csv
    ├── trades_round_3_day_0.csv
    ├── trades_round_3_day_1.csv
    └── trades_round_3_day_2.csv
```

---

## Setup

1. **Python 3.9+** — no external dependencies required for core pipeline.
   Optional but recommended:
   ```
   pip install scikit-learn numpy
   ```
   Without sklearn, `centroid.py` falls back to a built-in pure-Python DBSCAN.

2. **Place CSVs** in a folder called `round3_data/` next to the scripts.
   The simulator resolves this path relative to `simulator.py` automatically.
   Override with an environment variable if needed:
   ```
   ROUND3_DATA=/path/to/csvs python grid.py
   ```

3. **Your algo file** `r3.py` must be in the same directory.
   The provided `r3.py` is a fully functional starting strategy — see below.

---

## Usage — step by step

### Step 1 — Grid search
```bash
python grid.py
```
- Evaluates **225 parameter combinations** (5×5×3×3) against all 3 historical days.
- Saves results to `/tmp/grid_results.json` (~6 minutes total).
- Prints top-20 by mean P&L and by worst-day P&L (robustness proxy).

### Step 2 — Centroid analysis
```bash
python centroid.py
```
- Loads `/tmp/grid_results.json`.
- Defines the **plateau** = top 20% of grid points by mean P&L.
- Normalises each parameter to [0, 1], then runs **DBSCAN** to find the
  largest connected cluster of high-P&L points.
- Computes the **centroid** of that cluster and snaps it back to the nearest
  grid value per parameter.
- **Verifies** the centroid itself backtests in the plateau. If it falls in
  a hole (multimodal landscape), automatically falls back to the
  **densest-ball centre** — the cluster point whose neighbourhood has the
  highest mean P&L density.
- Prints a local gradient table (±1 grid step per param) so you can see
  sensitivity.
- Prints a ready-to-paste `RECOMMENDED = {...}` dict.

### Step 3 — Apply and verify
```bash
python apply_centroid.py
```
- Paste the `RECOMMENDED` dict from Step 2 into `apply_centroid.py`.
- Runs a final 3-day backtest with the exact centroid params.
- Prompts before patching `r3.py` constants in-place.

---

## Why centroid instead of top-1?

The **top-1 grid point** overfits to the 3 training days. A grid search
with 225 points will almost always find a parameter set that is simply lucky
on those days rather than genuinely better.

The **centroid of the plateau** is the geometric centre of the region where
many parameter combinations all perform well. This region is robust because:

- Any neighbour of the centroid is also high-P&L (by construction of the plateau).
- The centroid is unlikely to be an artefact of one day's price path.
- DBSCAN ensures the centroid belongs to a single connected mode, not the
  average of two unrelated optimal regions (multimodality).

The typical trade-off is 5–15% lower mean P&L versus top-1, in exchange for
much lower variance across unseen days.

---

## Simulator internals

`simulator.py` replays historical order-book snapshots against your `Trader`
class tick by tick.

### Fill model

| Order type | Fill condition |
|------------|---------------|
| **Aggressive** (price crosses book) | Fills immediately at quoted depth, up to order qty |
| **Passive** (price inside spread) | Fills if a market trade in that tick occurred at a compatible price — i.e., some other participant was aggressive enough to reach our level |

This is a **conservative** passive fill model. Real fills would be higher
because queue position, partial fills, and HFT flow are not modelled.
Treat simulated passive P&L as a lower bound.

### Mark-to-market

At the end of each day, all open positions are marked to the last observed
mid-price. This matches IMC's liquidation mechanic (positions are liquidated
against a hidden fair value at round end).

### Day isolation

Each day starts with the `traderData` string from the previous day (carrying
EMA state, IV estimates, flow signals). The position and cash carry over
across days within a single `run_with_params` call, matching the live
environment where inventory does not reset intra-round.

### Sampling

The simulator samples every 100th timestamp (`sample_step=100`) to keep
runtime reasonable. At 10,000 ticks per day × 3 days = 30,000 state
evaluations per backtest. One full 225-point grid run takes ~6 minutes.

---

## Trading strategy — r3.py

### HYDROGEL_PACK

- **EMA fair value**: exponential moving average of mid-price with
  `HYDROGEL_EMA_ALPHA` (default 0.05 = slow). This acts as the "true" price
  around which we market-make.
- **Passive quotes**: bid and ask placed `±4` ticks around the EMA fair value,
  adjusted by inventory skew and flow signal.
- **Aggressive take**: if the best bid exceeds `fair + HYDROGEL_TAKE_EDGE` or
  the best ask is below `fair - HYDROGEL_TAKE_EDGE`, we cross the spread to
  capture the edge immediately.

### VELVETFRUIT_EXTRACT

- Tighter EMA (alpha=0.10) for faster tracking of the more liquid product.
- **Flow-filtered quoting**: if the fast order-flow EMA signals strong buying
  pressure, we suppress our passive ask (don't sell into momentum); and
  vice versa.
- Half-spread of 2 ticks; aggressive edge of 3 ticks.

### VEV Option Vouchers

- **Black-Scholes fair value**: European call with `r=0`, using:
  - `S` = current VELVETFRUIT_EXTRACT mid
  - `K` = strike (4000 – 6500)
  - `T` = time-to-expiry in years (`TTE_days / 365`)
  - `σ` = implied volatility, updated each tick by averaging IV across
    all liquid strikes via Newton-Raphson solve, then EMA-smoothed
- **Aggressive mispricing trades**: if market mid deviates from BS fair value
  by more than `max(0.5, spread × 0.4)`, we cross to capture the edge.
- **Passive quotes**: post bid/ask at `fair ± half_spread` only if our quote
  improves the current book. This ensures we add liquidity rather than
  simply copying the existing market.
- **Inventory skew**: all three product types shift quotes toward reducing
  position when approaching the limit.

### Time-to-expiry (TTE)

The vouchers expire at the end of Round 7. Historical data covers days 0–2
(tutorial through Round 2), where:

| Historical day | TTE at day start |
|---------------|-----------------|
| 0 (tutorial)  | 8 days           |
| 1 (Round 1)   | 7 days           |
| 2 (Round 2)   | 6 days           |
| **3 (Round 3 live)** | **5 days** |

The simulator trains on days 0–2 (TTE 8–6). Live Round 3 uses TTE=5 — theta
decay is faster, so out-of-the-money options will be worth less than in the
training data. Keep this in mind when interpreting backtest P&L.

---

## Grid search parameters

| Parameter | Range searched | Effect |
|-----------|---------------|--------|
| `HYDROGEL_EMA_ALPHA` | 0.05 – 0.25 | Faster α → tracks price faster but is noisier |
| `HYDROGEL_TAKE_EDGE` | 6 – 14 | Higher edge → fewer but higher-quality aggressive fills |
| `MAX_TAKE_PER_TICK` | 3, 5, 8 | Controls how much we take per tick aggressively |
| `SKEW_HEAVY` | 0.30 – 0.50 | How aggressively we skew quotes to reduce heavy inventory |

Fixed baseline parameters (not searched — less sensitive from prior analysis):

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `VEV_IV_PRIOR` | 0.27 | Starting IV estimate (~27% annualised) |
| `FLOW_GATE_TICKS` | 2 | Ticks of sustained flow before triggering |
| `FLOW_FAST_N` | 3 | Fast EMA window for flow imbalance |
| `FLOW_SLOW_N` | 15 | Slow EMA window for flow imbalance |
| `MAX_PASSIVE_QTY` | 12 | Passive quote size per side |
| `SKEW_LIGHT` | 0.20 | Light inventory skew coefficient |

---

## Limitations and known issues

1. **No `r3.py` = no backtest** — the simulator imports your algo module.
2. **Passive fills are underestimated** — our model requires an actual market
   trade at the tick to fill passive orders. Real queue dynamics would fill more.
3. **TTE mismatch** — training TTE is 6–8 days; live is 5. BS values for OTM
   options will be systematically slightly higher in backtest than in live.
4. **Grid is 4-D** — only 4 of 11 parameters are searched. Extend `GRID` in
   `grid.py` and `centroid.py` if you want to search others (runtime scales
   multiplicatively).
5. **No transaction costs** — IMC charges no fees, so this is accurate.
