"""Functions for analyzing and visualizing trade and price data with optional
denoising.
"""

from typing import Callable, Any
from collections import defaultdict

import re

import pandas as pd

import matplotlib.pyplot as plt
import mplcursors

from vizdata.denoise import DENOISING_STRATEGIES, THRESHOLDING_STRATEGIES, not_identity


# -- PRIVATE HELPERS ----------------------------------------------------------

def _formatter(value: Any, discard: Any):
    """Format a numeric value as an integer string for axis ticks."""
    return f"{int(value)}"


def _make_plots(title: str, rows: int, cols: int, denoised: bool):
    """Create a subplot grid and a full-width bottom axis for combined series.

    The last row of the grid is removed and replaced by ``axes_master``, which
    spans the figure width for overlaying all items.

    Args:
        title: Figure suptitle and window title.
        rows: Number of subplot rows requested before the bottom strip is
        repurposed.
        cols: Number of columns.

    Returns:
        ``(fig, axes, axes_master)`` where ``axes`` is the remaining grid
        (without the bottom row) and ``axes_master`` is the bottom summary
        axis in lieu of the original bottom row.
    """
    fig, axes = plt.subplots(rows, cols, figsize=(16, 8), squeeze=False)
    try:
        fig.canvas.manager.set_window_title(title)  # type: ignore
    except AttributeError:
        print("Warning: Unable to set window title; feature may be unsupported in this environment.")
    fig.suptitle(title)

    for ax in axes[-1]:
        ax.remove()
    axes_master = fig.add_subplot(rows, 1, rows)
    axes_master.set_title(f"All Items{' (denoised)' if denoised else ''}")
    axes_master.xaxis.set_major_formatter(_formatter)
    axes_master.yaxis.set_major_formatter(_formatter)

    return fig, axes, axes_master


def _plot_data(
        axis,
        timestamps: list[int],
        data: list[int | float],
        data_label: str,
        data_color: str,
        artists: list | None = None,
        axis_color: str | None = None,
        title: str | None = None,
        title_color: str | None = None,
        show_legend: bool = False
        ):
    """Plot one series on an axis and append line artists for interactive
    cursors.

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
    axis.xaxis.set_major_formatter(_formatter)
    axis.yaxis.set_major_formatter(_formatter)
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
    if artists is not None:
        artists.extend(plot)

    if axis_color:
        axis.tick_params(axis="y", labelcolor=axis_color)
    if show_legend:
        axis.legend()


# -- ANALYSIS HELPER FUNCTIONS ------------------------------------------------

# MAJOR TODO: Refactor the analysis functions to directly operate on DataFrames

def _analyze_trade_data(
        data: pd.DataFrame,
        denoiser: Callable[[list[int | float]], list[int | float]]
        ):
    """Plot per-symbol trade price and quantity, plus a combined price view.

    Expects trade rows loadable as ``TradeData`` (grouped by ``symbol``).
    Opens an interactive figure with hover annotations.

    Args:
        data: Trade history table.
        filename: Label used in the figure title (typically the source file
        name).

    Returns:
        None. Prints a message and returns early if there are no rows.
    """
    # Check if any data was loaded
    if len(data) == 0:
        print("No trade data found for analysis")
        return

    # Check if denoising is actually being done
    denoised = not_identity(denoiser)

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    _, axes, ax_master = _make_plots(
            "Trade Data Analysis",
            3,
            len(set(data["symbol"])),
            denoised
            )

    # Create arrays to store each artist for rendering the cursors
    price_artists = []
    quantity_artists = []
    master_artists = []

    # render each individual trade item in a subplot
    for plot, symbol in enumerate(sorted(set(data["symbol"]))):
        mask = data["symbol"] == symbol
        # set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[1, plot].set_xlabel("Timestamp")  # type: ignore
        timestamps = data.loc[mask, "timestamp"].to_list()

        # plot the trade data
        prices = denoiser(data.loc[mask, "price"].to_list())
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title=f"price{' (denoised)' if denoised else ''}",
            title_color="green",
            timestamps=timestamps,
            data=prices,
            data_label="price",
            data_color="green",
            artists=price_artists
            )

        # plot the quantity data
        quantities = denoiser(data.loc[mask, "quantity"].to_list())
        _plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title=f"quantity{' (denoised)' if denoised else ''}",
            title_color="blue",
            timestamps=timestamps,
            data=quantities,
            data_label="quantity",
            data_color="blue",
            artists=quantity_artists
            )

        # plot the price on the master plot
        master_artists.extend(
                ax_master.plot(
                    timestamps,
                    prices,
                    label=symbol,
                    picker=8
                )
            )

    # create cursor for the price plot
    price_cursor = mplcursors.cursor(
            price_artists,
            hover=mplcursors.HoverMode.Transient
            )

    @price_cursor.connect("add")
    def on_add_price(sel):
        """Annotate hover selection on a price subplot."""
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nPrice{' (denoised)' if denoised else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightgreen")

    # create cursor for the quantity plot
    quantity_cursor = mplcursors.cursor(
            quantity_artists,
            hover=mplcursors.HoverMode.Transient
            )

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
        """Annotate hover selection on a quantity subplot."""
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nQuantity{' (denoised)' if denoised else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # create master cursor
    master_cursor = mplcursors.cursor(
            ax_master,
            hover=mplcursors.HoverMode.Transient
            )

    @master_cursor.connect("add")
    def on_add_master(sel):
        """Annotate hover selection on the combined master axis."""
        x, y = sel.target
        sel.annotation.set_text(f"Item: {sel.artist.get_label()}\nTimestamp: {x}\nPrice{' (denoised)' if denoised else ''}: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    # actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


def _analyze_price_data(
        data: pd.DataFrame,
        alpha: float,
        denoiser: Callable[[list[int | float]], list[int | float]]
        ):
    """Plot per-product bid/ask/fair price and volumes, plus combined price
    series.

    Expects rows loadable as ``PriceData`` (grouped by ``product``).
    Opens an interactive figure with hover annotations.

    Args:
        data: Price / order-book history table.
        filename: Label used in the figure title (typically the source file
        name).

    Returns:
        None. Prints a message and returns early if there are no rows.
    """

    # Check if any data was loaded
    if len(data) == 0:
        print("No price data found for analysis")
        return

    # Check if denoising is actually being done
    denoised = not_identity(denoiser)

    # Create a subplot for each price item
    # Rows 1-3 show price, bid volume, and ask volume data for each price item
    # Row 4 contains a master subplot of all the price items
    _, axes, ax_master = _make_plots(
            "Price Data Analysis",
            4,
            len(set(data["product"])),
            denoised
            )

    # Create arrays to store each artist for rendering the cursors
    bid_price_artists = []
    ask_price_artists = []
    mid_artists = []
    bid_quantity_artists = []
    ask_quantity_artists = []
    bid_master_artists = []
    ask_master_artists = []
    mid_master_artists = []

    # Compute masks for rows with nonzero bid/ask volumes and mid price
    # Avoid plotting zero values to reduce noise
    nonzero_bids = pd.notna(
            data["bid_volume_1"] +
            data["bid_volume_2"] +
            data["bid_volume_3"]
            ) & (
            data["bid_volume_1"] +
            data["bid_volume_2"] +
            data["bid_volume_3"] > 0
            )
    nonzero_asks = pd.notna(
            data["ask_volume_1"] +
            data["ask_volume_2"] +
            data["ask_volume_3"]
            ) & (
                data["ask_volume_1"] +
                data["ask_volume_2"] +
                data["ask_volume_3"] > 0
                )
    # No mid volume, so check the price to see if information is available
    nonzero_mid = data["mid_price"] > 0

    # Render each individual price item in a subplot
    for plot, symbol in enumerate(sorted(set(data["product"]))):
        mask = symbol == data["product"]
        # Set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[2, plot].set_xlabel("Timestamp")  # type: ignore

        bid_timestamps = data.loc[mask & nonzero_bids, "timestamp"].to_list()
        ask_timestamps = data.loc[mask & nonzero_asks, "timestamp"].to_list()
        mid_timestamps = data.loc[mask & nonzero_mid, "timestamp"].to_list()

        # Plot the bid/ask/fair value price data
        bid_prices = denoiser(data.loc[mask & nonzero_bids, ["bid_price_1", "bid_price_2", "bid_price_3"]].mean(axis=1).to_list())
        ask_prices = denoiser(data.loc[mask & nonzero_asks, ["ask_price_1", "ask_price_2", "ask_price_3"]].mean(axis=1).to_list())
        mid_prices = denoiser(data.loc[mask & nonzero_mid, "mid_price"].to_list())
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title=f"Bid/Ask Prices{' (denoised)' if denoised else ''}",
            title_color="green",
            timestamps=bid_timestamps,
            data=bid_prices,
            data_label="bid",
            data_color="green",
            artists=bid_price_artists,
            show_legend=True
            )
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=ask_timestamps,
            data=ask_prices,
            data_label="ask",
            data_color="red",
            artists=ask_price_artists,
            show_legend=True
            )
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=mid_timestamps,
            data=mid_prices,
            data_label="fair value",
            data_color="blue",
            artists=mid_artists,
            show_legend=True
            )

        # Plot EMA only if the denoising strategy is identity
        if not denoised:
            ema_prices = data.loc[mask & nonzero_mid, "mid_price"].ewm(alpha=alpha).mean().to_list()
            _plot_data(
                axis=axes[0, plot],  # type: ignore
                timestamps=mid_timestamps,
                data=ema_prices,
                data_label=f"EMA (alpha={alpha})",
                data_color="yellow",
                show_legend=True
                )

        # Plot the bid quantity data
        bid_volumes = denoiser(data.loc[mask & nonzero_bids, ["bid_volume_1", "bid_volume_2", "bid_volume_3"]].mean(axis=1).to_list())
        _plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title=f"Bid Volume{' (denoised)' if denoised else ''}",
            title_color="blue",
            timestamps=bid_timestamps,
            data=bid_volumes,
            data_label="bid",
            data_color="blue",
            artists=bid_quantity_artists
            )

        # Plot the ask quantity data
        ask_volumes = denoiser(data.loc[mask & nonzero_asks, ["ask_volume_1", "ask_volume_2", "ask_volume_3"]].mean(axis=1).to_list())
        _plot_data(
            axis=axes[2, plot],  # type: ignore
            axis_color="orange",
            title=f"Ask Volume{' (denoised)' if denoised else ''}",
            title_color="orange",
            timestamps=ask_timestamps,
            data=ask_volumes,
            data_label="ask",
            data_color="orange",
            artists=ask_quantity_artists
            )

        # Plot the bid/ask/fair value price on the master plot
        bid_master_artists.extend(
                ax_master.plot(
                    bid_timestamps,
                    bid_prices,
                    linewidth=0.8,
                    label=f"{symbol} bid",
                    picker=8
                )
            )
        ask_master_artists.extend(
                ax_master.plot(
                    ask_timestamps,
                    ask_prices,
                    linewidth=0.8,
                    label=f"{symbol} ask",
                    picker=8
                )
            )
        mid_master_artists.extend(
                ax_master.plot(
                    mid_timestamps,
                    mid_prices,
                    linewidth=0.8,
                    label=f"{symbol} fair value",
                    color="blue",
                    picker=8
                )
            )

    # Create cursor for the price plot
    price_cursor = mplcursors.cursor(
            [*bid_price_artists, *ask_price_artists, *mid_artists],
            hover=mplcursors.HoverMode.Transient
            )

    @price_cursor.connect("add")
    def on_add_price(sel):
        """Annotate hover selection on bid/ask/fair price lines."""
        x, y = sel.target
        label = sel.artist.get_label()
        if label == "bid":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Price{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif label == "ask":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Price{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nFair Value{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Create cursor for the quantity plot
    quantity_cursor = mplcursors.cursor(
            [*bid_quantity_artists, *ask_quantity_artists],
            hover=mplcursors.HoverMode.Transient
            )

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
        """Annotate hover selection on bid/ask volume lines."""
        x, y = sel.target
        label = sel.artist.get_label()
        if label == "bid":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Volume{' (denoised)' if denoised else ''}: {int(y)}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Volume{' (denoised)' if denoised else ''}: {int(y)}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    # Create master cursor
    master_cursor = mplcursors.cursor(
            [
                *bid_master_artists,
                *ask_master_artists,
                *mid_master_artists,
                ],
            hover=mplcursors.HoverMode.Transient
            )

    @master_cursor.connect("add")
    def on_add_master(sel):
        """Annotate hover selection on the combined master price lines."""
        x, y = sel.target
        symbol, trade_type = sel.artist.get_label().split(' ', 1)
        if trade_type == "bid":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nBid Price{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif trade_type == "ask":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nAsk Price{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nFair Value{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


def analyze_data(
        file_paths: list[str],
        strategy: str,
        passes: int,
        thresholding: str,
        alpha: float
        ):
    """Load a semicolon-separated CSV and dispatch to trade or price
    visualization.

    Chooses ``analyze_trade_data`` if a ``buyer`` column exists,
    ``analyze_price_data`` if ``profit_and_loss`` exists; otherwise prints a
    notice.
    Applies the appropriate denoising strategy if specified.

    Args:
        file_path: Path to the CSV file.
        strategy: The name of the denoising strategy to utilize
        passes: The number of denoising passes to make

    Returns:
        None.
    """

    trade_paths = defaultdict(pd.DataFrame)
    price_paths = defaultdict(pd.DataFrame)
    day_regex = re.compile(r"(?<=day_)-?\d+")

    for file_path in file_paths:
        data = pd.read_csv(file_path, sep=';')
        match = day_regex.search(file_path)
        if not match:
            print(f"Warning: File {file_path} does not contain a valid day number")
            continue
        day = int(match.group())
        if "buyer" in data.columns:
            trade_paths[day] = data
        elif "profit_and_loss" in data.columns:
            price_paths[day] = data
        else:
            print(f"Warning: File {file_path} is not a valid trade or price data file")

    # Determine the appropriate denoising function based on the strategy
    try:
        thresh = THRESHOLDING_STRATEGIES[thresholding]
        denoise = DENOISING_STRATEGIES[strategy](passes, thresh, alpha)
    except ValueError as e:
        print(f"Error: {e}. Defaulting to no denoising and hanning thresholding.")
        thresh = THRESHOLDING_STRATEGIES["hanning"]
        denoise = DENOISING_STRATEGIES["identity"](passes, thresh, alpha)

    if len(trade_paths) > 0:
        # Offset timestamps by day to ensure they are plotted chronologically
        for i, day in enumerate(sorted(set(trade_paths.keys()))):
            trade_paths[day]["timestamp"] += i * 1_000_000

        trade_data = pd.concat(trade_paths.values(), ignore_index=True).sort_values("timestamp")
        _analyze_trade_data(trade_data, denoise)

    if len(price_paths) > 0:
        # Offset timestamps by day to ensure they are plotted chronologically
        for i, day in enumerate(sorted(set(price_paths.keys()))):
            price_paths[day]["timestamp"] += i * 1_000_000

        price_data = pd.concat(price_paths.values(), ignore_index=True).sort_values("timestamp")

        _analyze_price_data(price_data, alpha, denoise)

    if len(trade_paths) == 0 and len(price_paths) == 0:
        print("No valid trade or price data found for analysis")
