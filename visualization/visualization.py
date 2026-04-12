# pyright: reportUnusedFunction=false

import argparse
import sys
import os

from typing import Any, Callable
from collections import defaultdict

import pandas as pd
import math
import statistics

import matplotlib.pyplot as plt
import mplcursors


# -- FOURIER TRANSFORM DENOISING ----------------------------------------------

def identity_denoise(passes: int = 1):
    """Return a function that performs no denoising and returns the input data as-is.

    Args:
        passes: Ignored; included for interface consistency with other denoising functions.

    Returns:
        A function that takes a list of numeric values and returns the same list unchanged.
    """
    def identity(data: list[int | float]):
        """Return the input data as-is without any denoising.

        Args:
            data: Sequence of numeric values.

        Returns:
            The same list of values unchanged.
        """
        return data

    return identity


def haar_denoise(passes: int = 1):
    """Return a function that applies a simple Haar wavelet transform to denoise a numeric series.

    Args:
        passes: The number of times to apply the Haar transform; more passes result in stronger denoising.

    Returns:
        A function that takes a list of numeric values and returns a denoised list of the same length.
    """
    def haar(data: list[int | float]):
        """Apply a simple Haar wavelet transform to denoise a numeric series.

        Args:
            data: Sequence of numeric values.

        Returns:
            List of denoised values.
        """
        # Store a list of the detail coefficients for reconstruction
        cD_list = []

        # Define common lamdas used throughout the denoise
        pair = lambda li: [(li[i], li[i + 1]) for i in range(0, len(li) - 1, 2)] + ([(li[-1], li[-1])] if len(li) % 2 == 1 else [])
        flatten = lambda pairs: [x for pair in pairs for x in pair]

        # Start with the approximations being the current data
        cA_list = data

        # Compute the coefficients for the specified number of passes
        for _ in range(passes):
            # Pair up the current approximation list and pad as needed
            cA_pairs = pair(cA_list)
            # Compute each pass's detail coefficients
            cDs = [(x - y) / math.sqrt(2) for x, y in cA_pairs]
            # Apply a threshold to transform the detail coefficients
            threshold = (statistics.median([abs(cD) for cD in cDs]) / 0.67448975) * math.sqrt(2 * math.log(len(cDs)))
            cDs = [math.copysign(1, cD) * max(abs(cD) - threshold, 0) for cD in cDs]
            # Store the coefficients for reconstruction
            cD_list.append(cDs)
            # Compute the next approximation coefficients
            cA_list = [(x + y) / math.sqrt(2) for x, y in cA_pairs]

        # Store the final computed approximations as the last layer
        # Reconstruct the denoised signal
        for coefficients in reversed(cD_list):
            cA_list= flatten([((cA + cD) / math.sqrt(2), (cA - cD) / math.sqrt(2)) for cA, cD in zip(cA_list, coefficients)])

        return cA_list

    return haar


# -- HELPER FUNCTIONS ---------------------------------------------------------

def castable(value, to_type):
    """Return whether ``value`` can be converted with ``to_type`` without error.

    Args:
        value: Value to convert.
        to_type: Callable used like ``to_type(value)`` (e.g. ``float``, ``int``).

    Returns:
        True if conversion succeeds; False if ``ValueError`` or ``TypeError`` is raised.
    """
    try:
        to_type(value)
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def avg(values: list):
    """Compute the mean of values that are finite and castable to float.

    Entries that are NaN or not castable to ``float`` are omitted.

    Args:
        values: Iterable of values to average.

    Returns:
        Arithmetic mean of the kept values, or ``0`` if none qualify.
    """
    actual = list(filter(lambda v: pd.notna(v) and castable(v, float), values))
    return sum(map(float, actual)) / len(actual) if actual else 0


def load_object(obj: type, data: pd.DataFrame, dict: dict[Any, list], key: str):
    """Build ``obj`` instances from dataframe rows and group them by a column key.

    Each row is passed to ``obj`` as keyword arguments. After loading, each list
    is sorted by a ``timestamp`` attribute.

    Args:
        obj: Class to instantiate for each row (must accept row fields as kwargs).
        data: Source table.
        dict: Mapping from ``row[key]`` to lists of instances; updated in place.
        key: Column name whose values are the grouping keys.

    Returns:
        None.
    """
    for _, row in data.iterrows():
        dict[row[key]].append(obj(**row.to_dict()))  # type: ignore

    for obj_list in dict.values():
        obj_list.sort()


def make_plots(title: str, rows: int, cols: int):
    """Create a subplot grid and a full-width bottom axis for combined series.

    The last row of the grid is removed and replaced by ``axes_master``, which spans
    the figure width for overlaying all items.

    Args:
        title: Figure suptitle.
        rows: Number of subplot rows requested before the bottom strip is repurposed.
        cols: Number of columns.

    Returns:
        ``(fig, axes, axes_master)`` where ``axes`` is the remaining grid (without
        the bottom row) and ``axes_master`` is the bottom summary axis.
    """
    fig, axes = plt.subplots(rows, cols, figsize=(16, 8), squeeze=False)
    fig.suptitle(title)
    formatter = lambda v, _: f"{int(v)}"

    for ax in axes[-1]:
        ax.remove()
    axes_master = fig.add_subplot(rows, 1, rows)
    axes_master.set_title("All Items")
    axes_master.xaxis.set_major_formatter(formatter)
    axes_master.yaxis.set_major_formatter(formatter)

    return fig, axes, axes_master


def plot_data(
        axis,
        timestamps: list[int],
        data: list[int | float],
        data_label: str,
        data_color: str,
        artists: list,
        axis_color: str | None = None,
        title: str | None = None,
        title_color: str | None = None,
        show_legend: bool = False
        ):
    """Plot one series on an axis and append line artists for interactive cursors.

    Args:
        axis: Target matplotlib axes.
        timestamps: X coordinates.
        data: Y coordinates.
        data_label: Label used in the legend when enabled.
        data_color: Line color.
        artists: Mutable list extended with the line artist(s) from this plot.
        axis_color: If set, colors the y-axis tick labels.
        title: If set with ``title_color``, used as the y-axis label.
        title_color: Color for the y-axis label when ``title`` is provided.
        show_legend: Whether to call ``legend()`` on the axis.

    Returns:
        None.
    """
    formatter = lambda v, _: f"{int(v)}"

    axis.xaxis.set_major_formatter(formatter)
    axis.yaxis.set_major_formatter(formatter)
    if title and title_color:
        axis.set_ylabel(title, color=title_color)
    plot = axis.plot(
        timestamps,
        data,
        linewidth=0.8,
        label=data_label,
        color=data_color,
        picker=8
    )
    artists.extend(plot)

    if axis_color:
        axis.tick_params(axis="y", labelcolor=axis_color)
    if show_legend:
        axis.legend()


def not_identity(callback: Callable[[list[int | float]], list[int | float]]):
    """Return whether the provided callback is not the identity denoising function.

    Args:
        callback: Denoising function to check.

    Returns:
        True if the callback is not the identity function; False if it is.
    """
    return callback.__qualname__ != identity_denoise(1).__qualname__


# -- DATA CLASSES -------------------------------------------------------------

class TradeData:
    """One trade row: timestamp, symbol, quantity, and price."""

    def __init__(
            self,
            **kwargs
            ):
        """Initialize from keyword arguments for the expected CSV columns.

        Args:
            **kwargs: Must include ``timestamp``, ``symbol``, ``quantity``, and ``price``.
        """
        self.timestamp = int(kwargs["timestamp"])
        self.symbol = str(kwargs["symbol"])
        self.quantity = int(kwargs["quantity"])
        self.price = float(kwargs["price"])

    def __lt__(self, other):
        """Return whether this trade is earlier than ``other`` by timestamp."""
        return self.timestamp < other.timestamp


class PriceData:
    """One order-book snapshot with averaged bid/ask prices and volumes."""

    def __init__(
            self,
            **kwargs
            ):
        """Initialize from keyword arguments; top three bid/ask levels are averaged.

        Args:
            **kwargs: Must include ``timestamp``, ``product``, ``bid_price_*``,
                ``ask_price_*``, ``bid_volume_*``, and ``ask_volume_*`` fields used below.
        """
        self.timestamp = int(kwargs["timestamp"])
        self.product = str(kwargs["product"])
        self.bid_price = avg([kwargs["bid_price_1"], kwargs["bid_price_2"], kwargs["bid_price_3"]])
        self.ask_price = avg([kwargs["ask_price_1"], kwargs["ask_price_2"], kwargs["ask_price_3"]])
        self.bid_volume = avg([kwargs["bid_volume_1"], kwargs["bid_volume_2"], kwargs["bid_volume_3"]])
        self.ask_volume = avg([kwargs["ask_volume_1"], kwargs["ask_volume_2"], kwargs["ask_volume_3"]])

    def __lt__(self, other):
        """Return whether this update is earlier than ``other`` by timestamp."""
        return self.timestamp < other.timestamp


# -- TOP-LEVEL CONSTANTS ------------------------------------------------------

DENOISING_STRATEGIES = {
    "identity": identity_denoise,
    "haar": haar_denoise
}


# -- ANALYSIS FUNCTIONS -------------------------------------------------------

def analyze_trade_data(data: pd.DataFrame, filename: str, denoise_callback: Callable[[list[int | float]], list[int | float]]):
    """Plot per-symbol trade price and quantity, plus a combined price view.

    Expects trade rows loadable as ``TradeData`` (grouped by ``symbol``).
    Opens an interactive figure with hover annotations.

    Args:
        data: Trade history table.
        filename: Label used in the figure title (typically the source file name).

    Returns:
        None. Prints a message and returns early if there are no rows.
    """
    trades = defaultdict(list)
    load_object(TradeData, data, trades, "symbol")

    # Check if any data was loaded
    if not trades:
        print("No trade data found for analysis")
        return

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    _, axes, ax_master = make_plots(f"Trade Data Analysis for {filename}", 3, len(trades.items()))

    # Create arrays to store each artist for rendering the cursors
    price_artists = []
    quantity_artists = []
    master_artists = []

    # Render each individual trade item in a subplot
    for plot, (symbol, trade_list) in enumerate(trades.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[1, plot].set_xlabel("Timestamp")  # type: ignore
        timestamps = [trade.timestamp for trade in trade_list]

        # Plot the trade data
        prices = denoise_callback([trade.price for trade in trade_list])
        plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title="Price",
            title_color="green",
            timestamps=timestamps,
            data=prices,
            data_label="Price",
            data_color="green",
            artists=price_artists
            )

        # Plot the quantity data
        quantities = denoise_callback([trade.quantity for trade in trade_list])
        plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title="Quantity",
            title_color="blue",
            timestamps=timestamps,
            data=quantities,
            data_label="Quantity",
            data_color="blue",
            artists=quantity_artists,
            )

        # Plot the price on the master plot
        master_artists.extend(
                ax_master.plot(
                    timestamps,
                    prices,
                    label=symbol,
                    picker=8
                )
            )

    # Create cursor for the price plot
    price_cursor = mplcursors.cursor(price_artists, hover=mplcursors.HoverMode.Transient)

    @price_cursor.connect("add")
    def on_add_price(sel):
        """Annotate hover selection on a price subplot."""
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nPrice{' (denoised)' if not_identity(denoise_callback) else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightgreen")

    # Create cursor for the quantity plot
    quantity_cursor = mplcursors.cursor(quantity_artists, hover=mplcursors.HoverMode.Transient)

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
        """Annotate hover selection on a quantity subplot."""
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nQuantity{' (denoised)' if not_identity(denoise_callback) else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Create master cursor
    master_cursor = mplcursors.cursor(ax_master, hover=mplcursors.HoverMode.Transient)

    @master_cursor.connect("add")
    def on_add_master(sel):
        """Annotate hover selection on the combined master axis."""
        x, y = sel.target
        sel.annotation.set_text(f"Item: {sel.artist.get_label()}\nTimestamp: {x}\nPrice{' (denoised)' if not_identity(denoise_callback) else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    # Actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


def analyze_price_data(data: pd.DataFrame, filename: str, denoise_callback: Callable[[list[int | float]], list[int | float]]):
    """Plot per-product bid/ask/fair price and volumes, plus combined price series.

    Expects rows loadable as ``PriceData`` (grouped by ``product``).
    Opens an interactive figure with hover annotations.

    Args:
        data: Price / order-book history table.
        filename: Label used in the figure title (typically the source file name).

    Returns:
        None. Prints a message and returns early if there are no rows.
    """
    prices = defaultdict(list)
    load_object(PriceData, data, prices, "product")

    # Check if any data was loaded
    if not prices:
        print("No price data found for analysis")
        return

    # Create a subplot for each price item
    # Rows 1-3 show price, bid volume, and ask volume data for each price item
    # Row 4 contains a master subplot of all the price items
    _, axes, ax_master = make_plots(f"Price Data Analysis for {filename}", 4, len(prices.items()))

    # Create arrays to store each artist for rendering the cursors
    bid_price_artists = []
    ask_price_artists = []
    fair_value_artists = []
    bid_quantity_artists = []
    ask_quantity_artists = []
    bid_master_artists = []
    ask_master_artists = []
    fair_value_master_artists = []

    # Render each individual price item in a subplot
    for plot, (symbol, price_list) in enumerate(prices.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[2, plot].set_xlabel("Timestamp")  # type: ignore
        timestamps = [price.timestamp for price in price_list]

        # Plot the bid/ask/fair value price data
        bid_prices = denoise_callback([price.bid_price for price in price_list])
        ask_prices = denoise_callback([price.ask_price for price in price_list])
        fair_value_prices = denoise_callback([(price.bid_price + price.ask_price) / 2 for price in price_list])
        plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title="Bid/Ask Price",
            title_color="green",
            timestamps=timestamps,
            data=bid_prices,
            data_label="bid",
            data_color="green",
            artists=bid_price_artists,
            show_legend=True
            )
        plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=timestamps,
            data=ask_prices,
            data_label="ask",
            data_color="red",
            artists=ask_price_artists,
            show_legend=True
            )
        plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=timestamps,
            data=fair_value_prices,
            data_label="fair value",
            data_color="blue",
            artists=fair_value_artists,
            show_legend=True
            )

        # Plot the bid quantity data
        bid_volumes = denoise_callback([price.bid_volume for price in price_list])
        plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title="Bid Volume",
            title_color="blue",
            timestamps=timestamps,
            data=bid_volumes,
            data_label="bid",
            data_color="blue",
            artists=bid_quantity_artists
            )

        # Plot the ask quantity data
        ask_volumes = denoise_callback([price.ask_volume for price in price_list])
        plot_data(
            axis=axes[2, plot],  # type: ignore
            axis_color="orange",
            title="Ask Volume",
            title_color="orange",
            timestamps=timestamps,
            data=ask_volumes,
            data_label="ask",
            data_color="orange",
            artists=ask_quantity_artists
            )

        # Plot the bid/ask/fair value price on the master plot
        bid_master_artists.extend(
                ax_master.plot(
                    timestamps,
                    bid_prices,
                    linewidth=0.8,
                    label=f"{symbol} bid",
                    picker=8
                )
            )
        ask_master_artists.extend(
                ax_master.plot(
                    timestamps,
                    ask_prices,
                    linewidth=0.8,
                    label=f"{symbol} ask",
                    picker=8
                )
            )
        fair_value_master_artists.extend(
                ax_master.plot(
                    timestamps,
                    fair_value_prices,
                    linewidth=0.8,
                    label=f"{symbol} fair value",
                    color="blue",
                    picker=8
                )
            )

    # Create cursor for the price plot
    price_cursor = mplcursors.cursor([*bid_price_artists, *ask_price_artists, *fair_value_artists], hover=mplcursors.HoverMode.Transient)

    @price_cursor.connect("add")
    def on_add_price(sel):
        """Annotate hover selection on bid/ask/fair price lines."""
        x, y = sel.target
        label = sel.artist.get_label()
        if label == "bid":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Price{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif label == "ask":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Price{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nFair Value{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Create cursor for the quantity plot
    quantity_cursor = mplcursors.cursor([*bid_quantity_artists, *ask_quantity_artists], hover=mplcursors.HoverMode.Transient)

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
        """Annotate hover selection on bid/ask volume lines."""
        x, y = sel.target
        label = sel.artist.get_label()
        if label == "bid":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Volume{' (denoised)' if not_identity(denoise_callback) else ''}: {int(y)}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Volume{' (denoised)' if not_identity(denoise_callback) else ''}: {int(y)}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    # Create master cursor
    master_cursor = mplcursors.cursor([*bid_master_artists, *ask_master_artists, *fair_value_master_artists], hover=mplcursors.HoverMode.Transient)

    @master_cursor.connect("add")
    def on_add_master(sel):
        """Annotate hover selection on the combined master price lines."""
        x, y = sel.target
        symbol, type = sel.artist.get_label().split(' ', 1)
        if type == "bid":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nBid Price{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif type == "ask":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nAsk Price{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nFair Value{' (denoised)' if not_identity(denoise_callback) else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


def analyze_data(file_path: str, strategy: str, passes: int):
    """Load a semicolon-separated CSV and dispatch to trade or price visualization.

    Chooses ``analyze_trade_data`` if a ``buyer`` column exists,
    ``analyze_price_data`` if ``profit_and_loss`` exists; otherwise prints a notice.
    Applies the appropriate denoising strategy if specified.

    Args:
        file_path: Path to the CSV file.
        strategy: The name of the denoising strategy to utilize
        passes: The number of denoising passes to make

    Returns:
        None.
    """
    # Read the pandas data
    data = pd.read_csv(file_path, sep=";")

    # Determine the appropriate denoising function based on the strategy argument
    denoise = DENOISING_STRATEGIES[strategy](passes)

    if "buyer" in data.columns:
        analyze_trade_data(data, os.path.basename(file_path), denoise)
    elif "profit_and_loss" in data.columns:
        analyze_price_data(data, os.path.basename(file_path), denoise)
    else:
        print("Unknown data being analyzed")


# -- CLI ----------------------------------------------------------------------

def main():
    """Parse CLI paths and run ``analyze_data`` on each existing file."""

    parser = argparse.ArgumentParser(description="Visualize trade and price data from CSV files.")
    parser.add_argument("default_files", nargs="+", help="Paths to CSV files for analysis")
    parser.add_argument("--files", "-f", dest="files", nargs="*", help="Paths to CSV files for analysis explicitly specified with --files")
    parser.add_argument("--denoise", "-d", dest="denoise", action="store_true", help="Denoise the data before plotting")
    parser.add_argument("--strategy", "-s", dest="strategy", choices=list(DENOISING_STRATEGIES.keys()), default="identity", help="Which Fourier transform to utilize when denoising the data")
    parser.add_argument("--passes", "-p", dest="passes", type=int, default=2, help="The number of passes to perform the Fourier transform for")

    args = parser.parse_args()
    # Can only pass --strength and --passes if --denoise is an argument
    denoise_args = [arg for arg in ["--strategy", "-s", "--passes", "-p"] if arg in sys.argv]
    if denoise_args and not args.denoise:
        parser.error(f"{' '.join(denoise_args)} cannot be specified if --denoise isn't passed")
    # Parsing files must be passed
    to_parse = args.files + args.default_files if args.files and args.default_files else args.files or args.default_files
    if not to_parse:
        parser.error("No files to parse")
    # If denoising, default strategy is haar
    denoise_strategy = "haar" if args.denoise and ("--strategy" not in sys.argv and "-s" not in sys.argv) else args.strategy

    files = []
    for file in to_parse:
        if os.path.isfile(file):
            files.append(file)
        else:
            parser.error(f"Unknown file: {file}")

    for file in files:
        analyze_data(file, denoise_strategy, args.passes)


if __name__ == "__main__":
    main()
