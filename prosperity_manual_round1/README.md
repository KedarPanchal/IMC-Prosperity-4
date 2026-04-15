# Intarian Welcome — auction EV enumeration

Python tools for the manual challenge **“An Intarian Welcome”**: uniform-price call auction with **max traded volume**, then **highest clearing price** tie-break, and **price–time priority** (you submit **last**).

TLDR BRUTEFORCE RESULTS

```bash
=== DRYLAND_FLAX top long / short ===
best_long: {'side': 'bid', 'limit_price': 30, 'quantity': 9999, 'profit': 9999.0, 'clearing_price': 29.0, 'user_filled_qty': 9999}
best_short: {'side': 'ask', 'limit_price': 29, 'quantity': 1, 'profit': 0.0, 'clearing_price': 28.0, 'user_filled_qty': 0}
best_short_positive_fill: {'side': 'ask', 'limit_price': 25, 'quantity': 1, 'profit': -2.0, 'clearing_price': 28.0, 'user_filled_qty': 1}
long >= short profit: True

=== EMBER_MUSHROOM top long / short ===
best_long: {'side': 'bid', 'limit_price': 17, 'quantity': 19999, 'profit': 77996.09999999999, 'clearing_price': 16.0, 'user_filled_qty': 19999}
best_short: {'side': 'ask', 'limit_price': 15, 'quantity': 1, 'profit': -0.0, 'clearing_price': 15.0, 'user_filled_qty': 0}
best_short_positive_fill: {'side': 'ask', 'limit_price': 10, 'quantity': 1, 'profit': -5.1, 'clearing_price': 15.0, 'user_filled_qty': 1}
long >= short profit: True
```

## Setup

From this repository’s root (the folder that contains `requirements.txt`):

```powershell
cd IMC-Prosperity-4\prosperity_manual_round1
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe -m intarian_welcome --out output\intarian_welcome
```

After `Activate.ps1`, the same command is `python -m intarian_welcome --out output\intarian_welcome`.

Useful flags (full list: `python -m intarian_welcome --help`):

| Flag | Meaning |
|------|--------|
| `--out DIR` | Output directory for CSV, JSON, PNGs |
| `--no-heatmap` | Skip matplotlib PNG heatmaps (faster) |
| `--dense-through N` | Include every integer quantity `1..N` (capped by `--qty-cap`) so knife-edge sizes like `4999` / `19999` are not missed |
| `--random-samples K` | Merge `K` extra uniform random `(side, price, qty)` candidates |

Example: quick run without heatmaps:

```powershell
.\.venv\Scripts\python.exe -m intarian_welcome --out output\intarian_welcome --no-heatmap
```

### Outputs per product

- `DRYLAND_FLAX_all_candidates.csv`, `EMBER_MUSHROOM_all_candidates.csv`
- `*_summary.json` — best long, best short, best short with **positive fill**, knife-edge checks on top candidates
- `*_heatmap_bid_long.png`, `*_heatmap_ask_short.png` if heatmaps enabled (quantity axis may be subsampled for file size)

## Modeling assumptions

- **Limit bids** → long into the call; **post-auction** buyback at **30** (flax) and **20** (mushroom).
- **Ember mushroom fee:** the code subtracts **0.10** per filled unit on the **buyback / cover** leg (`fee_long` and `fee_short` in `ProductParams` inside `run_analysis.py`). That matches a **0.10 total** round-trip fee per unit taken on the post-auction leg. If your rules state **0.05 on the auction leg and 0.05 on the buyback**, the **total** drag is often still **0.10** per unit; in that case the aggregate economics usually align with this single **0.10** term. If your rules differ (fee on one leg only, non-flat fees, etc.), change `ProductParams` accordingly.
- **Flax:** no fee in the model (`fee_long` / `fee_short` = 0).
- **Limit asks** are treated as **shorts** covered at the same buyback prices. If your game rules differ, adjust `ProductParams` and/or the simulator logic.

## Order book snapshots

Resting liquidity (price → aggregate size) is defined in **`intarian_welcome/frozen_books.py`**. It is a **manual snapshot**: update that file when the challenge book changes, then re-run the analysis.

## Package layout

`intarian_welcome/` — `frozen_books`, `clearing_simulator`, `ev_enumeration`, `run_analysis`, `__main__.py` (CLI).
