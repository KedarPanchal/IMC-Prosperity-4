# IMC Prosperity 4 Visualizer

This tool opens interactive matplotlib windows to explore IMC Prosperity 4 CSV data (trade logs or price/orderbook logs). You can zoom/pan like a normal chart, and you can hover points to see the exact timestamp/value.

## What you need first

- A terminal (macOS Terminal, Windows PowerShell, etc.)
- This repository cloned/downloaded
- One or more IMC Prosperity CSV files you want to view

## Install `uv` (dependency manager)

`uv` installs and runs Python dependencies for you.

### macOS

Option A (Homebrew, recommended if you already use it):

```bash
brew install uv
```

Option B (installer script):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

Run this in **PowerShell**:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Verify `uv` works

```bash
uv --version
```

If that prints a version number, you’re good.

## Install the visualizer’s dependencies (one-time)

From the repository root, go into the `visualization` folder and install dependencies:

```bash
cd visualization
uv sync
```

`uv sync` may take a minute the first time. After it finishes, you typically won’t need to do it again unless the project’s dependencies change.

## Run: interactive visualization (`analysis`)

Stay in the `visualization` folder and run:

```bash
uv run visualization.py analysis -f path/to/file1.csv path/to/file2.csv
```

Notes:

- The CSVs are expected to be **semicolon-separated** (`;`) (this is how IMC Prosperity exports are typically formatted).
- The program will open **one interactive window per file**. Close the current window to move to the next file.
- Files must be passed via `--files` / `-f` (positional file arguments are not supported).

```bash
uv run visualization.py analysis --files path/to/file1.csv path/to/file2.csv
```

- If a file looks “wrong”, it may be the other dataset type. The program decides which view to show based on the columns it finds:
  - Trade-style CSVs (it detects a `buyer` column) show price + quantity per symbol, plus a combined “master” price plot.
  - Price/orderbook-style CSVs (it detects a `profit_and_loss` column) show bid/ask/fair value and volumes, plus a combined “master” plot.

## Optional: denoise for feature extraction and trend analysis

Financial data often contains short-lived “noise” (tiny fluctuations, microstructure effects, random jumps) that can hide the bigger picture. Denoising is a way to **extract higher-level features**—like broader trends, regime changes, and persistent moves—by reducing that short-term noise before plotting.

### Choose a denoising strategy

```bash
uv run visualization.py analysis -f path/to/file.csv --strategy haar
```

Supported strategies:

- `haar`: Haar wavelet denoising
- `identity`: no denoising (default)

### Control denoising strength with `--passes`

`--passes` controls how strong the smoothing is (default is `2`).

```bash
uv run visualization.py analysis -f path/to/file.csv --strategy haar --passes 4
```

Impact of changing `--passes`:

- **Lower passes (e.g. 1–2)**: keeps more detail; small wiggles and short-lived moves remain visible.
- **Higher passes (e.g. 3–6)**: smoother curves; short spikes get reduced or removed.
- **Too high**: the chart can become “over-smoothed”, where real turning points are flattened and fast moves look delayed or muted.

## Run: bot clustering (`classification`)

There is also a clustering-based helper to group “bots” based on trading behavior using k-means clustering.

It expects **matching trade + price CSVs** for the same day(s):

- Trade logs (filenames typically contain `trades`) provide executed trades (e.g., `buyer`, `seller`, `price`, `quantity`).
- Price/orderbook logs (filenames typically contain `prices`) provide mid-price/market state (e.g., `mid_price`).

The classifier also expects the filenames to include a day marker like `day_0`, `day_1`, etc., so it can line up days correctly.

### What the clustering “looks at”

The clustering is based on simple behavior features computed per symbol over short time buckets, including:

- **Price shape**: open/close, high/low, return, and range (from `mid_price`)
- **Activity**: total traded volume, number of trades, and average trade size
- **Symbol exposure**: which products were being traded (one-hot encoded)

Before clustering, the features are standardized (so different scales don’t dominate), reduced to 2D with PCA for visualization, and then grouped using k-means.

Run:

```bash
uv run visualization.py classification -f path/to/day_0_trades.csv path/to/day_0_prices.csv
```

Tune cluster count (default \(k=10\)):

```bash
uv run visualization.py classification -f path/to/day_0_trades.csv path/to/day_0_prices.csv --clusters 15
```

## Troubleshooting

- If you get “Unknown file”: double-check the path and that the file exists.
- If nothing shows up: make sure the window isn’t opening behind other windows; also confirm you’re running from the `visualization` folder.
- If the chart looks empty or says it found no data: you may have provided a CSV with unexpected columns/formatting.
- If you see “Unknown data being analyzed”: the CSV didn’t match the expected schemas (trade files need a `buyer` column; price/orderbook files need a `profit_and_loss` column).
