# Intarian Welcome — auction EV enumeration

Python tools for the manual challenge **“An Intarian Welcome”**: uniform-price call auction with **max traded volume**, then **highest clearing price** tie-break, and **price–time priority** (you submit **last**).

TLDR RESULTS

```bash
=== DRYLAND_FLAX top long / short ===
best_long: {'side': 'bid', 'limit_price': 30, 'quantity': 9999, 'profit': 9999.0, 'clearing_price': 29.0, 'user_filled_qty': 9999}
best_short: {'side': 'ask', 'limit_price': 29, 'quantity': 1, 'profit': 0.0, 'clearing_price': 28.0, 'user_filled_qty': 0}
best_short_positive_fill: {'side': 'ask', 'limit_price': 27, 'quantity': 1, 'profit': -2.0, 'clearing_price': 28.0, 'user_filled_qty': 1}
long >= short profit: True

=== EMBER_MUSHROOM top long / short ===
best_long: {'side': 'bid', 'limit_price': 17, 'quantity': 19999, 'profit': 77996.09999999999, 'clearing_price': 16.0, 'user_filled_qty': 19999}
best_short: {'side': 'ask', 'limit_price': 15, 'quantity': 1, 'profit': -0.0, 'clearing_price': 16.0, 'user_filled_qty': 0}
best_short_positive_fill: {'side': 'ask', 'limit_price': 12, 'quantity': 1, 'profit': -4.1, 'clearing_price': 16.0, 'user_filled_qty': 1}
long >= short profit: True
```


## Setup

```powershell
cd \prosperity_manual_2
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python -m intarian_welcome --out output\intarian_welcome
```

Options (see `intarian_welcome/run_analysis.py`):

- `--dense-through N` — include **every** integer quantity `1..N` (capped by `--qty-cap`) so knife-edge sizes like `4999` / `19999` are not missed.
- `--no-heatmap` — skip PNG heatmaps.
- `--random-samples K` — merge `K` uniform random `(side, price, qty)` candidates.

Outputs per product:

- `DRYLAND_FLAX_all_candidates.csv`, `EMBER_MUSHROOM_all_candidates.csv`
- `*_summary.json` — best long, best short, best short with **positive fill**, knife-edge checks on top candidates
- `*_heatmap_bid_long.png`, `*_heatmap_ask_short.png` (quantity axis may be subsampled for file size)

## Modeling assumptions

- **Limit bids** → long into the call; **post-auction** buyback at **30** (flax) **20** (mushroom) with mushroom **0.10** fee on the buyback leg.
- **Limit asks** are treated as **shorts** covered at the same buyback prices (see plan). If your game rules differ, adjust `ProductParams` in `run_analysis.py`.

## Package layout

`intarian_welcome/` — `frozen_books`, `clearing_simulator`, `ev_enumeration`, `run_analysis`.
