# Visualization Tool

The visualization tool is designed to visualize IMC Prosperity 4 trade and price data.
It's a simple matplotlib-based visualizer that relies on the default interface for data exploration.


## Prerequisites

Ensure you have `uv` installed to manage your Python environment.
You can install it on macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternatively, you can install it with Homebrew (recommended for macOS users):

```bash
brew install uv
```

You can also install it with pip:

```bash
pip install uv
```

After installing `uv`, you can install the required dependencies for the visualization tool:

```bash
uv sync
```

## Usage

To run the visualization tool, use the following command:

```bash
uv run visualization.py <filenames>
```

Where `<filenames>` is a space-delimited list of pandas-compatible data files (e.g., CSV) containing the IMC Prosperity 4 trade and price data.

Running the command opens up a matplotlib window with the visualizations of the provided data files.
You can interact with the visualizations using the default matplotlib interface, allowing you to explore the data in various ways (e.g., zooming, panning, etc.).

Each data file will be visualized in a separate plot window sequentially.
This means that to advance to the next file view, you will need to close the current plot window.
