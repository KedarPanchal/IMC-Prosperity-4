# IMC Prosperity 4 Visualizer

This tool opens an interactive window to explore IMC Prosperity 4 CSV data (trades or prices). You can zoom/pan like a normal chart, and you can hover points to see the exact timestamp/value.

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

## Run the visualizer

Stay in the `visualization` folder and run:

```bash
uv run visualization.py path/to/file1.csv path/to/file2.csv
```

Notes:

- The CSVs are expected to be **semicolon-separated** (`;`) (this is how IMC Prosperity exports are typically formatted).
- The program will open **one interactive window per file**. Close the current window to move to the next file.
- You can also pass files using `--files` / `-f` (this is optional, but can help if you prefer flag-style arguments):

```bash
uv run visualization.py --files path/to/file1.csv path/to/file2.csv
```

- If a file looks “wrong”, it may be the other dataset type. The program decides which view to show based on the columns it finds:
  - Trade-style CSVs (it detects a `buyer` column) show price + quantity per symbol, plus a combined “master” price plot.
  - Price/orderbook-style CSVs (it detects a `profit_and_loss` column) show bid/ask/fair value and volumes, plus a combined “master” plot.

## Optional: denoise for feature extraction and trend analysis

Financial data often contains short-lived “noise” (tiny fluctuations, microstructure effects, random jumps) that can hide the bigger picture. Denoising is a way to **extract higher-level features**—like broader trends, regime changes, and persistent moves—by reducing that short-term noise before plotting.

### Turn denoising on

```bash
uv run visualization.py --denoise path/to/file.csv
```

When you pass `--denoise`:

- The charts will emphasize **trend and structure** (useful for feature extraction and analysis).
- Some short, sharp events can be reduced or removed (so don’t use denoising if you need to study individual spikes/ticks).
- If you do not pass `--denoise`, the raw data is plotted.

### Choose a denoising strategy

Currently supported strategies:

- `haar`: Haar wavelet denoising (the default when `--denoise` is enabled)
- `identity`: effectively “no denoising” (useful for comparisons)

Example:

```bash
uv run visualization.py --denoise --strategy haar path/to/file.csv
```

Important:

- `--strategy` only works if you also include `--denoise`. If you try to use `--strategy` without `--denoise`, the program will stop with an error.

### Control denoising strength with `--passes`

`--passes` controls how strong the smoothing is (default is `2`).

```bash
uv run visualization.py --denoise --passes 4 path/to/file.csv
```

Impact of changing `--passes`:

- **Lower passes (e.g. 1–2)**: keeps more detail; small wiggles and short-lived moves remain visible.
- **Higher passes (e.g. 3–6)**: smoother curves; short spikes get reduced or removed.
- **Too high**: the chart can become “over-smoothed”, where real turning points are flattened and fast moves look delayed or muted.

Important:

- `--passes` only works if you also include `--denoise`. If you try to use `--passes` without `--denoise`, the program will stop with an error.

## Troubleshooting

- If you get “Unknown file”: double-check the path and that the file exists.
- If nothing shows up: make sure the window isn’t opening behind other windows; also confirm you’re running from the `visualization` folder.
- If the chart looks empty or says it found no data: you may have provided a CSV with unexpected columns/formatting.
