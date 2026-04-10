# Backtesting

The backtester calls one of three backtesters for testing Prosperity 4 strategies.
All backtesters are built off of jmerle's Prosperity 3 backtester.

The backtesters are:

* `prosperity4btx` - ZEESHAN's Prosperity 4 backtester
* `prosperity4btest` - Nabayan Saha's Prosperity 4 backtester
* `prosperity3bt` - Jmerle's Prosperity 3 backtester

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

These dependencies are installed and updated by the backtesting script, so this step is optional.

## Usage

To run the backtesting tool, use the following command:

```bash
bash backtest.sh <backtester> <options>
```

Where `<backtester>` is one of the following:

* `zeeshan` - ZEESHAN's Prosperity 4 backtester
* `nabayan` - Nabayan Saha's Prosperity 4 backtester
* `jmerle` - Jmerle's Prosperity 3 backtester

And `<options>` are the supported options for the selected backtester.
All backtesters support the same options.
You can view the supported options for each backtester by running:

```bash
bash backtest.sh --help
```

Or, you can run:

```bash
bash backtest.sh <backtester> --help
```
