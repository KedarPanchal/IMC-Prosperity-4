# pyright: reportUnusedFunction=false

import argparse
import sys
import os

from typing import Callable
from collections import defaultdict

import pandas as pd

import matplotlib.pyplot as plt
import mplcursors

from vizdata.plotting import make_plots, plot_data
from vizdata.denoise import DENOISING_STRATEGIES, not_identity
from vizdata.datamodels import TradeData, PriceData, load_object


def analyze_trade_data(
        data: pd.DataFrame,
        filename: str,
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
    trades = defaultdict(list)
    load_object(TradeData, data, trades, "symbol")

    # Check if any data was loaded
    if not trades:
        print("No trade data found for analysis")
        return

    # Check if denoising is actually being done
    denoised = not_identity(denoiser)

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    _, axes, ax_master = make_plots(
            f"Trade Data Analysis for {filename}",
            3,
            len(trades.items()),
            denoised
            )

    # Create arrays to store each artist for rendering the cursors
    price_artists = []
    quantity_artists = []
    master_artists = []

    # render each individual trade item in a subplot
    for plot, (symbol, trade_list) in enumerate(trades.items()):
        # set shared axis data
        axes[0, plot].set_title(symbol)  # type: ignore
        axes[1, plot].set_xlabel("Timestamp")  # type: ignore
        timestamps = [trade.timestamp for trade in trade_list]

        # plot the trade data
        prices = denoiser([trade.price for trade in trade_list])
        plot_data(
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
        quantities = denoiser([trade.quantity for trade in trade_list])
        plot_data(
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


def analyze_price_data(
        data: pd.DataFrame,
        filename: str,
        denoiser: Callable[[list[int | float]], list[int | float]]
        ):
    """plot per-product bid/ask/fair price and volumes, plus combined price
    series.

    expects rows loadable as ``pricedata`` (grouped by ``product``).
    opens an interactive figure with hover annotations.

    Args:
        data: Price / order-book history table.
        filename: Label used in the figure title (typically the source file
        name).

    Returns:
        None. Prints a message and returns early if there are no rows.
    """
    prices = defaultdict(list)
    load_object(PriceData, data, prices, "product")

    # Check if any data was loaded
    if not prices:
        print("No price data found for analysis")
        return

    # Check if denoising is actually being done
    denoised = not_identity(denoiser)

    # Create a subplot for each price item
    # Rows 1-3 show price, bid volume, and ask volume data for each price item
    # Row 4 contains a master subplot of all the price items
    _, axes, ax_master = make_plots(
            f"Price Data Analysis for {filename}",
            4,
            len(prices.items()),
            denoised
            )

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
        bid_prices = denoiser([price.bid_price for price in price_list])
        ask_prices = denoiser([price.ask_price for price in price_list])
        fair_value_prices = denoiser([(price.bid_price + price.ask_price) / 2 for price in price_list])
        plot_data(
            axis=axes[0, plot],  # type: ignore
            axis_color="green",
            title=f"Bid/Ask Prices{' (denoised)' if denoised else ''}",
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
        bid_volumes = denoiser([price.bid_volume for price in price_list])
        plot_data(
            axis=axes[1, plot],  # type: ignore
            axis_color="blue",
            title=f"Bid Volume{' (denoised)' if denoised else ''}",
            title_color="blue",
            timestamps=timestamps,
            data=bid_volumes,
            data_label="bid",
            data_color="blue",
            artists=bid_quantity_artists
            )

        # Plot the ask quantity data
        ask_volumes = denoiser([price.ask_volume for price in price_list])
        plot_data(
            axis=axes[2, plot],  # type: ignore
            axis_color="orange",
            title=f"Ask Volume{' (denoised)' if denoised else ''}",
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
    price_cursor = mplcursors.cursor(
            [*bid_price_artists, *ask_price_artists, *fair_value_artists],
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
                *fair_value_master_artists,
                ],
            hover=mplcursors.HoverMode.Transient
            )

    @master_cursor.connect("add")
    def on_add_master(sel):
        """Annotate hover selection on the combined master price lines."""
        x, y = sel.target
        symbol, type = sel.artist.get_label().split(' ', 1)
        if type == "bid":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nBid Price{' (denoised)' if denoised else ''}: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif type == "ask":
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


def analyze_data(file_path: str, strategy: str, passes: int):
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
    # Read the pandas data
    data = pd.read_csv(file_path, sep=";")

    # Determine the appropriate denoising function based on the strategy
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

    parser = argparse.ArgumentParser(
            description="Visualize trade and price data from CSV files."
            )
    parser.add_argument(
            "default_files",
            nargs="*",
            help="Paths to CSV files for analysis"
            )
    parser.add_argument(
            "--files",
            "-f",
            dest="files",
            nargs="*",
            help="Paths to CSV files for analysis"
            )
    parser.add_argument(
            "--denoise",
            "-d",
            dest="denoise",
            action="store_true",
            help="Denoise the data before plotting"
            )
    parser.add_argument(
            "--strategy",
            "-s",
            dest="strategy",
            choices=list(DENOISING_STRATEGIES.keys()),
            default="identity",
            help="Which denoising algorithm to utilize when denoising the data"
            )
    parser.add_argument(
            "--passes",
            "-p",
            dest="passes",
            type=int,
            default=2,
            help="The number of passes to perform the Fourier transform for"
            )

    args = parser.parse_args()
    # Can only pass --strength and --passes if --denoise is an argument
    # TODO: This sucks absolute ass, reimplement with argument groups
    #       This will also make adding bot classification much easier
    denoise_args = [
            arg
            for arg in ["--strategy", "-s", "--passes", "-p"]
            if arg in sys.argv
            ]
    if denoise_args and not args.denoise:
        parser.error(
            f"{' '.join(denoise_args)} can't be used if --denoise isn't passed",
            )
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
