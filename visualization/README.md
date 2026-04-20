# IMC Prosperity 4 Visualizer

This tool opens interactive charts to explore IMC Prosperity 4 CSV data (trades and/or prices). You can zoom and pan like a normal chart, and you can hover points to see the exact timestamp/value.

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

- These CSVs are usually **semicolon-separated** (`;`) (that’s the standard IMC export format).
- If you pass multiple files, the tool will group them into sensible charts:
  - Trade files show trade prices/quantities by product, plus an overall “master” price view.
  - Price/orderbook files show bid/ask/fair value and volumes, plus an overall “master” view.
  - If you pass both types, you’ll typically get **two windows** (one for trades, one for prices).
- Files must be passed via `--files` / `-f` (positional arguments aren’t supported).

```bash
uv run visualization.py analysis --files path/to/file1.csv path/to/file2.csv
```

- If a chart looks “wrong”, you may have passed the other dataset type. The tool auto-detects the file type from its columns.
- If you pass multiple days of data, filenames should include a day marker like `day_0`, `day_1`, etc., so the tool can plot days in the right order.

## Optional: denoise for feature extraction and trend analysis

Market data is often “wiggly” at short time scales. Denoising helps you see the **bigger picture** (trend, broad moves, and turning points) by smoothing out small, fast fluctuations before plotting.

### Choose a denoising strategy

```bash
uv run visualization.py analysis -f path/to/file.csv --strategy haar
```

Supported strategies (high-level):

- `identity` (default): no smoothing, raw data
- `ema`: a simple smoothing option that reacts gradually to changes
- `haar`: a stronger “de-noise the bumps” option that can make the line cleaner
- `dft`: frequency-based smoothing (often good for removing rapid oscillations, but see the note below)

### Thresholding (optional): a filter applied after every pass

Thresholding is an **extra filter applied after every smoothing pass**. In plain terms: it helps reduce the small “leftover” noise after each pass.

Choose a thresholding style with `--thresholding` / `-t`:

- `soft`: gently tapers values down in a **non-aggressive** way (a good general-purpose choice)
- `hanning` (default): applies a smooth Hanning-style window across the **whole series** (useful when you want a consistent “global” smoothing effect)

Example:

```bash
uv run visualization.py analysis -f path/to/file.csv --strategy dft --passes 3 --thresholding hanning
```

### Control denoising strength with `--passes`

`--passes` controls how strong the smoothing is (default is `2`). More passes usually means a smoother line, with diminishing returns.

```bash
uv run visualization.py analysis -f path/to/file.csv --strategy haar --passes 4
```

- If the chart still looks noisy, increase `--passes`.
- If the chart feels “laggy” or misses sharp moves/turns, reduce `--passes`.

#### Note on `dft` artifacts (edge tail dropoffs)

`dft` can sometimes create **start/end “tail” dropoffs**, due to the data entries not exactly aligning with the "frequency" the algorithm assigns to it. If you see that, try fewer `--passes` or switch to `ema` or `haar`.

## Run: bot clustering (`classification`)

There is also a helper that groups “bots” by similar trading behavior (a quick way to spot who trades similarly).

It expects **matching trade + price CSVs** for the same day(s):

- Trade logs (filenames typically contain `trades`) provide executed trades (e.g., `buyer`, `seller`, `price`, `quantity`).
- Price/orderbook logs (filenames typically contain `prices`) provide the market state (including `mid_price`).

The classifier expects filenames to include a day marker like `day_0`, `day_1`, etc., so it can line up days correctly.

### What clustering uses (high-level)

It summarizes each trader’s behavior (per product and over time) using simple signals like:

- How active they are (how often / how much they trade)
- Whether they tend to buy vs sell
- How their trading lines up with price moves

Run:

```bash
uv run visualization.py classification -f path/to/day_0_trades.csv path/to/day_0_prices.csv
```

Notes:

- You must provide the **same set of days** for trades and prices. If you pass trades for 2 days but prices for only 1 day (or vice versa), the classifier will stop with an error.
- If a file is missing a `day_#` marker in its name, it will be skipped.

Tune cluster count (default \(k=10\)):

```bash
uv run visualization.py classification -f path/to/day_0_trades.csv path/to/day_0_prices.csv --clusters 15
```

## Troubleshooting

- If you get “Unknown file”: double-check the path and that the file exists.
- If nothing shows up: make sure the window isn’t opening behind other windows; also confirm you’re running from the `visualization` folder.
- If the chart looks empty or says it found no data: you may have provided a CSV with unexpected columns/formatting.
- If you see “Unknown data being analyzed”: the CSV didn’t match the expected schemas (trade files need a `buyer` column; price/orderbook files need a `profit_and_loss` column).
- If `classification` says it processed a different number of trade vs price files: make sure you passed a **matching trades+prices pair for every day**, and that each filename contains `day_#`.
