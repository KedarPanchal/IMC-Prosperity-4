"""Functions for analyzing and visualizing trade and price data with optional
denoising.
"""

from typing import Any
from collections import defaultdict

import re

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.widgets as widgets
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import mplcursors

from vizdata.denoise import DENOISING_STRATEGIES


# -- PRIVATE HELPERS ----------------------------------------------------------

def _collate(data: dict[Any, pd.DataFrame]):
    """Collate a dictionary of DataFrames into a single DataFrame sorted by
    timestamp.

    This function processes data across multiple days and alters timestamps
    such that later days have higher timestamp values.
    """
    if len(data) == 0:
        return pd.DataFrame()

    # Each day has 1 million timestamps
    for i, day in enumerate(sorted(set(data.keys()))):
        data[day]["timestamp"] += i * 1_000_000

    return pd.concat(data.values(), ignore_index=True).sort_values("timestamp")


def _formatter(value: Any, discard: Any):
    """Format a numeric value as an integer string for axis ticks."""
    return f"{int(value)}"


def _make_plots(title: str, rows: int, cols: int):
    """Create a subplot grid and a full-width bottom axis for combined series.

    The last row of the grid is a master axis with a shared x-axis and spans
    the figure width for overlaying all items.

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
    fig = plt.figure(figsize=(16, 8))
    gs = gridspec.GridSpec(
        nrows=rows + 1,
        ncols=cols + 1,
        figure=fig,
        left=0.05,
        right=0.95,
        top=0.9,
        bottom=0.1,
        wspace=0.25,
        hspace=0.5,
        width_ratios=[1.2] + [2] * cols,
        )
    try:
        fig.canvas.manager.set_window_title(title)  # type: ignore
    except AttributeError:
        print("Warning: Unable to set window title; feature may be unsupported in this environment.")

    fig.suptitle(title)

    control_axes = fig.add_subplot(gs[:, 0])
    control_axes.set_xticks([])
    control_axes.set_yticks([])
    control_axes.set_frame_on(False)

    axes = []
    for r in range(rows):
        row_axes = []
        for c in range(cols):
            ax = fig.add_subplot(gs[r, c + 1])
            ax.xaxis.set_major_formatter(_formatter)
            ax.yaxis.set_major_formatter(_formatter)
            row_axes.append(ax)
        axes.append(row_axes)

    axes_master = fig.add_subplot(gs[rows, 1:])
    axes_master.set_title("All Items")
    axes_master.xaxis.set_major_formatter(_formatter)
    axes_master.yaxis.set_major_formatter(_formatter)

    return fig, np.array(axes), axes_master, control_axes


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


def _denoise_gui(fig: Figure, axes: Axes, artists_list: list[list], raw_data_list: list[list]):
    """Renders a simple GUI with controls for denoising the plotted data using
    different strategies.

    Args:
        fig: The matplotlib figure to which the GUI will be attached.
        axes: The axes on which to place the GUI controls.
        artists_list: A list of lists of matplotlib line artists corresponding
        to the plotted data series.
        raw_data_list: A list of lists of raw data corresponding to each artist
        list, used for applying the denoising transformations.

    Returns:
        The created GUI controls (buttons and text boxes) since matplotlib
        requires keeping references to them to prevent garbage collection.
    """
    button_axes = axes.inset_axes((0.05, 0.4, 0.9, 0.15))
    button = widgets.RadioButtons(
            button_axes,
            labels=list(DENOISING_STRATEGIES.keys()),
            active=list(DENOISING_STRATEGIES.keys()).index("identity")
            )
    passes_axes = axes.inset_axes((0.25, 0.35, 0.7, 0.04))
    passes = widgets.TextBox(
            passes_axes,
            label="Passes: ",
            initial="6",
            )
    alpha_axes = axes.inset_axes((0.52, 0.3, 0.43, 0.04))
    alpha = widgets.TextBox(
            alpha_axes,
            label="Alpha (EMA only): ",
            initial="0.5",
            )

    def change_denoise(label):
        try:
            passes_value = int(passes.text)
            alpha_value = float(alpha.text)
        except ValueError:
            print("Invalid input for denoising passes and/or alpha; using default of 6 passes and 0.5 alpha")
            passes_value = 6
            alpha_value = 0.5

        denoiser = DENOISING_STRATEGIES[label](passes_value, alpha_value)
        for artists, raw_data in zip(artists_list, raw_data_list):
            for artist, data in zip(artists, raw_data):
                artist.set_ydata(denoiser(data))
        fig.canvas.draw_idle()

    button.on_clicked(change_denoise)
    passes.on_submit(change_denoise)

    return button, passes, alpha


# -- ANALYSIS HELPER FUNCTIONS ------------------------------------------------

def _analyze_trade_data(
        data: pd.DataFrame,
        ):
    """Plot per-symbol trade price and quantity, plus a combined price view.

    Expects trade rows loadable as ``TradeData`` (grouped by ``symbol``).
    Opens an interactive figure with hover annotations.

    Args:
        data: Trade history table.

    Returns:
        None. Prints a message and returns early if there are no rows.
    """
    # Check if any data was loaded
    if len(data) == 0:
        print("No trade data found for analysis")
        return

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    fig, axes, ax_master, control_axes = _make_plots(
            "Trade Data Analysis",
            2,
            len(set(data["symbol"])),
            )

    # Create arrays to store each artist for rendering the cursors
    price_artists = []
    price_artists_data_raw = []
    quantity_artists = []
    quantity_artists_data_raw = []
    master_artists = []

    # render each individual trade item in a subplot
    for plot, symbol in enumerate(sorted(set(data["symbol"]))):
        mask = data["symbol"] == symbol
        # set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[1, plot].set_xlabel("Timestamp")  # type: ignore
        timestamps = data.loc[mask, "timestamp"].to_list()

        # plot the trade data
        price_artists_data_raw.append(data.loc[mask, "price"].to_list())
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title="price",
            title_color="green",
            timestamps=timestamps,
            data=price_artists_data_raw[-1],
            data_label="price",
            data_color="green",
            artists=price_artists
            )

        # plot the quantity data
        quantity_artists_data_raw.append(data.loc[mask, "quantity"].to_list())
        _plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title="quantity",
            title_color="blue",
            timestamps=timestamps,
            data=quantity_artists_data_raw[-1],
            data_label="quantity",
            data_color="blue",
            artists=quantity_artists
            )

        # plot the price on the master plot
        master_artists.extend(
                ax_master.plot(
                    timestamps,
                    price_artists_data_raw[-1],
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
        sel.annotation.set_text(f"Timestamp: {x}\nPrice: {y}")
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
        sel.annotation.set_text(f"Timestamp: {x}\nQuantity: {y}")
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
        sel.annotation.set_text(f"Item: {sel.artist.get_label()}\nTimestamp: {x}\nPrice: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    _ = _denoise_gui(
        fig,
        control_axes,
        artists_list=[price_artists, quantity_artists, master_artists],
        raw_data_list=[price_artists_data_raw, quantity_artists_data_raw, price_artists_data_raw]
        )
    # actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


def _analyze_price_data(data: pd.DataFrame):
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

    # Create a subplot for each price item
    # Rows 1-3 show price, bid volume, and ask volume data for each price item
    # Row 4 contains a master subplot of all the price items
    fig, axes, ax_master, control_axes = _make_plots(
            "Price Data Analysis",
            2,
            len(set(data["product"])),
            )

    # Create arrays to store each artist for rendering the cursors
    bid_price_artists = []
    bid_price_artists_data_raw = []
    ask_price_artists = []
    ask_price_artists_data_raw = []
    mid_price_artists = []
    mid_price_artists_data_raw = []
    bid_quantity_artists = []
    bid_quantity_artists_data_raw = []
    ask_quantity_artists = []
    ask_quantity_artists_data_raw = []
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
        axes[1, plot].set_xlabel("Timestamp")  # type: ignore

        bid_timestamps = data.loc[mask & nonzero_bids, "timestamp"].to_list()
        ask_timestamps = data.loc[mask & nonzero_asks, "timestamp"].to_list()
        mid_timestamps = data.loc[mask & nonzero_mid, "timestamp"].to_list()

        # Plot the bid/ask/fair value price data
        bid_price_artists_data_raw.append(data.loc[mask & nonzero_bids, ["bid_price_1", "bid_price_2", "bid_price_3"]].mean(axis=1).to_list())
        ask_price_artists_data_raw.append(data.loc[mask & nonzero_asks, ["ask_price_1", "ask_price_2", "ask_price_3"]].mean(axis=1).to_list())
        mid_price_artists_data_raw.append(data.loc[mask & nonzero_mid, "mid_price"].to_list())
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title="Bid/Ask Prices",
            title_color="green",
            timestamps=bid_timestamps,
            data=bid_price_artists_data_raw[-1],
            data_label="bid",
            data_color="green",
            artists=bid_price_artists,
            show_legend=True
            )
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=ask_timestamps,
            data=ask_price_artists_data_raw[-1],
            data_label="ask",
            data_color="red",
            artists=ask_price_artists,
            show_legend=True
            )
        _plot_data(
            axis=axes[0, plot],  # type: ignore
            timestamps=mid_timestamps,
            data=mid_price_artists_data_raw[-1],
            data_label="fair value",
            data_color="blue",
            artists=mid_price_artists,
            show_legend=True
            )

        # Plot the bid/ask quantity data
        bid_quantity_artists_data_raw.append(data.loc[mask & nonzero_bids, ["bid_volume_1", "bid_volume_2", "bid_volume_3"]].mean(axis=1).to_list())
        ask_quantity_artists_data_raw.append(data.loc[mask & nonzero_asks, ["ask_volume_1", "ask_volume_2", "ask_volume_3"]].mean(axis=1).to_list())
        _plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title="Bid/Ask Volume",
            title_color="blue",
            timestamps=bid_timestamps,
            data=bid_quantity_artists_data_raw[-1],
            data_label="bid",
            data_color="blue",
            artists=bid_quantity_artists,
            show_legend=True
            )
        _plot_data(
            axis=axes[1, plot],  # type: ignore
            timestamps=ask_timestamps,
            data=ask_quantity_artists_data_raw[-1],
            data_label="ask",
            data_color="orange",
            artists=ask_quantity_artists,
            show_legend=True
            )

        # Plot the bid/ask/fair value price on the master plot
        bid_master_artists.extend(
                ax_master.plot(
                    bid_timestamps,
                    bid_price_artists_data_raw[-1],
                    linewidth=0.8,
                    label=f"{symbol} bid",
                    picker=8
                )
            )
        ask_master_artists.extend(
                ax_master.plot(
                    ask_timestamps,
                    ask_price_artists_data_raw[-1],
                    linewidth=0.8,
                    label=f"{symbol} ask",
                    picker=8
                )
            )
        mid_master_artists.extend(
                ax_master.plot(
                    mid_timestamps,
                    mid_price_artists_data_raw[-1],
                    linewidth=0.8,
                    label=f"{symbol} fair value",
                    color="blue",
                    picker=8
                )
            )

    # Create cursor for the price plot
    price_cursor = mplcursors.cursor(
            [*bid_price_artists, *ask_price_artists, *mid_price_artists],
            hover=mplcursors.HoverMode.Transient
            )

    @price_cursor.connect("add")
    def on_add_price(sel):
        """Annotate hover selection on bid/ask/fair price lines."""
        x, y = sel.target
        label = sel.artist.get_label()
        if label == "bid":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif label == "ask":
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nFair Value: {float(y):.2f}")
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
            sel.annotation.set_text(f"Timestamp: {int(x)}\nBid Volume: {int(y)}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")
        else:
            sel.annotation.set_text(f"Timestamp: {int(x)}\nAsk Volume: {int(y)}")
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
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nBid Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif trade_type == "ask":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nAsk Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nFair Value: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

    # Render control panel
    _ = _denoise_gui(
        fig,
        control_axes,
        artists_list=[
            bid_price_artists,
            ask_price_artists,
            mid_price_artists,
            bid_quantity_artists,
            ask_quantity_artists,
            bid_master_artists,
            ask_master_artists,
            mid_master_artists
        ],
        raw_data_list=[
            bid_price_artists_data_raw,
            ask_price_artists_data_raw,
            mid_price_artists_data_raw,
            bid_quantity_artists_data_raw,
            ask_quantity_artists_data_raw,
            bid_price_artists_data_raw,
            ask_price_artists_data_raw,
            mid_price_artists_data_raw,
        ]
        )
    bid_ask_checkbox_axes = control_axes.inset_axes((0.05, 0.05, 0.9, 0.2))
    bid_ask_mapping = {
        "Show bid price": bid_price_artists + bid_master_artists,
        "Show ask price": ask_price_artists + ask_master_artists,
        "Show fair value price": mid_price_artists + mid_master_artists,
        "Show bid volume": bid_quantity_artists,
        "Show ask volume": ask_quantity_artists,
    }
    bid_ask_checkbox = widgets.CheckButtons(
        bid_ask_checkbox_axes,
        labels=list(bid_ask_mapping.keys()),
        actives=[True] * len(bid_ask_mapping.keys())
        )

    def toggle_bid_ask(label):
        for artist in bid_ask_mapping[label]:
            artist.set_visible(not artist.get_visible())
        fig.canvas.draw_idle()

    bid_ask_checkbox.on_clicked(toggle_bid_ask)

    # Actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


# -- MAIN ANALYSIS FUNCTION ---------------------------------------------------

def analyze_data(file_paths: list[str]):
    """Load a semicolon-separated CSV and dispatch to trade or price
    visualization.

    Chooses ``analyze_trade_data`` if a ``buyer`` column exists,
    ``analyze_price_data`` if ``profit_and_loss`` exists; otherwise prints a
    notice.

    Args:
        file_paths: Path to the CSV file.

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

    if len(trade_paths) > 0:
        trade_data = _collate(trade_paths)
        _analyze_trade_data(trade_data)

    if len(price_paths) > 0:
        price_data = _collate(price_paths)
        _analyze_price_data(price_data)

    if len(trade_paths) == 0 and len(price_paths) == 0:
        print("No valid trade or price data found for analysis")
