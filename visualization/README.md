# IMC Prosperity 4 Visualizer

This tool opens interactive charts to explore IMC Prosperity 4 CSV data (trades and/or prices). You can zoom and pan like a normal chart, and you can hover over points to see the exact timestamp and value.

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

If that prints a version number, you're good.

## Install the visualizer's dependencies (one-time)

From the repository root, go into the `visualization` folder and install dependencies:

```bash
cd visualization
uv sync
```

`uv sync` may take a minute the first time. After it finishes, you typically won't need to do it again unless the project's dependencies change.

---

## Running the tool

All commands follow this pattern (run from inside the `visualization` folder):

```
uv run visualization.py -f <file1.csv> [file2.csv ...] -m <mode>
```

- **`-f` / `--files`** — one or more CSV paths to load (required)
- **`-m` / `--mode`** — what to do with the data: `analysis` (default) or `classification`

### File naming requirements

Every CSV filename **must** include a day marker like `day_0`, `day_1`, `day_-1`, etc. The tool uses this to sort and stitch multiple days together in the right order. Files without a day marker are skipped with a warning.

> **Example good names:** `prices_day_0.csv`, `trades_day_1.csv`, `round2_day_-1_prices.csv`

---

## Mode: `analysis` — interactive price/trade charts

Loads the CSV files and opens one or two chart windows (one for trade data, one for price/orderbook data — whichever types you provided).

```bash
uv run visualization.py -f path/to/prices_day_0.csv path/to/trades_day_0.csv -m analysis
```

Or, since `analysis` is the default, you can omit `-m`:

```bash
uv run visualization.py -f path/to/prices_day_0.csv path/to/trades_day_0.csv
```

**Notes:**
- CSVs are **semicolon-separated** (`;`) — that's the standard IMC export format.
- The tool auto-detects whether a file is a trade file or a price/orderbook file based on its columns:
  - Trade files must have a `buyer` column.
  - Price/orderbook files must have a `profit_and_loss` column.
- If a chart looks wrong, you may have passed a file of the other type.
- If you pass multiple days of data, timestamps are stitched together so later days appear to the right on the chart.

### What you see in the chart

**Trade data window** (one subplot per product):
- **Row 1** — trade price over time (green)
- **Row 2** — trade quantity over time (blue)
- **Bottom strip** — all products' trade prices overlaid in one "All Items" view

**Price/orderbook data window** (one subplot per product):
- **Row 1** — bid price (green), ask price (red), and fair value/mid price (blue)
- **Row 2** — bid volume (blue) and ask volume (orange)
- **Bottom strip** — all products' bid, ask, and fair value prices overlaid

Hovering over any line shows a tooltip with the exact timestamp and value.

### Left-side control panel (analysis mode)

Both windows have a control panel on the left side. It lets you smooth the data live without re-running the tool.

#### Denoising strategy (radio buttons)

Choose how to smooth the plotted lines:

| Strategy | What it does |
|---|---|
| **identity** | No smoothing — shows raw data exactly as-is (default) |
| **ema** | Exponential Moving Average — reacts gradually to changes; gentler smoothing |
| **haar** | Haar wavelet — removes spiky noise while preserving sharper moves |
| **dft** | Discrete Fourier Transform — removes rapid oscillations using frequency filtering |

Click a radio button to apply the strategy immediately.

> **Note on `dft`:** It can sometimes produce a visible "dropoff" at the very start or end of the chart. If you see that, try `ema` or `haar` instead, or reduce the number of passes.

#### Passes (text box)

Controls how *strong* the smoothing is. Default is **6**.

- Type a number and press **Enter** to apply.
- Higher passes → smoother line, but may miss sharp turns.
- Lower passes → less smoothed, closer to raw data.

#### Alpha — EMA only (text box)

Only relevant when **ema** is selected. Default is **0.5**.

- Must be a decimal between 0 and 1 (exclusive).
- **Closer to 1** → reacts quickly to new data (less smoothing).
- **Closer to 0** → reacts slowly (more smoothing, more lag).

#### Show/hide checkboxes (price window only)

The price/orderbook window also has checkboxes to toggle individual series on and off:

| Checkbox | Toggles |
|---|---|
| **Show bid price** | Bid price lines in the per-product subplots and the "All Items" strip |
| **Show ask price** | Ask price lines in the per-product subplots and the "All Items" strip |
| **Show fair value price** | Mid/fair value price lines everywhere |
| **Show bid volume** | Bid volume lines in the volume subplot |
| **Show ask volume** | Ask volume lines in the volume subplot |

---

## Mode: `classification` — trading pattern clustering

Groups time windows of market activity into clusters based on price and volume behavior. Useful for spotting patterns like high-volatility periods, low-activity lulls, or unusual price moves.

### File requirements

Classification requires **both** trade files and price files for **the same set of days**:

- Trade filenames must contain the word **`trades`** somewhere in the name.
- Price filenames must contain the word **`prices`** somewhere in the name.
- Both must include a `day_#` marker.

If you provide trades for 2 days but prices for only 1 day (or vice versa), the tool will stop with an error.

```bash
uv run visualization.py -f path/to/trades_day_0.csv path/to/prices_day_0.csv -m classification
```

### What you see in the chart

The classification window shows a **scatter plot** where each dot represents a 2-second time window. The axes are two "PCA components" — mathematical summaries of the data that try to capture the most variation. Points that are close together behaved similarly during that window; points that are far apart behaved differently.

The dots are colored by cluster (group), and **Voronoi boundaries** are drawn between cluster centers to show where one group ends and another begins.

Hovering over a dot shows a tooltip with the time window's start timestamp and the key metrics that went into that point (mid-price open/close/high/low, total volume, number of trades, average trade size, and the assigned cluster).

### Left-side control panel (classification mode)

#### Number of Clusters (k) (text box)

How many groups to divide the data into. Default is **10**.

- Type a number and press **Enter** to recompute the clusters immediately.
- Fewer clusters → broader, coarser groups.
- More clusters → finer distinctions, but may over-split similar behavior.

#### Random Seed (text box)

K-means clustering has a small random component in how it picks starting points. The seed makes results reproducible. Default is **0**.

- Type any non-negative integer and press **Enter** to recompute.
- Changing the seed with the same k will sometimes give slightly different cluster assignments.

#### PCA Component breakdown

Below the controls, two colored info boxes show what metrics contribute most to each PCA axis:

- **PCA Component 1** (blue box) — the main axis of variation in the data.
- **PCA Component 2** (green box) — the secondary axis.

Each metric is listed with its percentage contribution. This helps you understand what the x/y axes actually mean (e.g., "Component 1 is mostly total volume and number of trades").

---

## Troubleshooting

- **"Unknown file"**: Double-check the path and that the file exists.
- **Nothing shows up / window opens behind others**: Make sure you're running from the `visualization` folder, and check that the chart window didn't open behind other windows.
- **Chart looks empty**: Confirm the CSV has actual data rows and uses semicolons (`;`) as the separator.
- **"Warning: File … does not contain a valid day number"**: Rename the file to include `day_0`, `day_1`, etc. in its filename.
- **"Warning: File … is not a valid trade or price data file"** (analysis mode): The CSV didn't match either expected schema. Trade files need a `buyer` column; price files need a `profit_and_loss` column.
- **"Warning: File … is not a valid trade or price dataframe"** (classification mode): The filename must contain `trades` or `prices` for the classifier to tell them apart.
- **"Error: Processed N trade dataframes but only M price dataframes"**: You didn't pass a matching trade+price pair for every day. Make sure each day has exactly one trades file and one prices file.
