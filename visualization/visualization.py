# pyright: reportUnusedFunction=false

import sys
import os
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt
import mplcursors
import numpy as np


# -- HELPER FUNCTIONS ---------------------------------------------------------

# Checks if a value can be cast to a given type
def castable(value, to_type):
    try:
        to_type(value)
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def avg(values: list):
    actual = list(filter(lambda v: pd.notna(v) and castable(v, float), values))
    return sum(map(float, actual)) / len(actual) if actual else 0


# -- ANALYSIS FUNCTIONS -------------------------------------------------------

class TradeData:
    def __init__(
            self,
            timestamp: int,
            symbol: str,
            quantity: int,
            price: float
            ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.quantity = quantity
        self.price = price

    def __lt__(self, other):
        return self.timestamp < other.timestamp


def analyze_trade_data(data: pd.DataFrame, filename: str):
    # Dictionary mapping trade items to their data by timestamp
    trades = defaultdict(list)
    for _, row in data.iterrows():
        trades[row["symbol"]].append(TradeData(
            int(row["timestamp"]),  # type: ignore
            str(row["symbol"]),
            int((row["quantity"])),  # type: ignore
            float(row["price"])  # type: ignore
        ))

    # Check if any data was loaded
    if not trades:
        print("No trade data found for analysis")
        return

    # Sort each trade item by timestamp
    for trade_list in trades.values():
        trade_list.sort()

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    fig, axes = plt.subplots(3, len(trades.items()), figsize=(12, 6))
    fig.suptitle(f"Trade Data Analysis for {filename}")
    for ax in axes[2]:
        ax.remove()
    ax_master = fig.add_subplot(3, 1, 3)

    # Create a main formatter applied to all axes
    main_formatter = lambda v, _: f"{int(v)}"

    # Set plot data for the master plot
    ax_master.xaxis.set_major_formatter(main_formatter)
    ax_master.yaxis.set_major_formatter(main_formatter)
    ax_master.set_title("All Trade Items")

    # Render each individual trade item in a subplot
    for plot, (symbol, trade_list) in enumerate(trades.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)
        axes[1, plot].set_xlabel("Timestamp")
        timestamps = [trade.timestamp for trade in trade_list]

        # Plot the trade data
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].xaxis.set_major_formatter(main_formatter)
        axes[0, plot].yaxis.set_major_formatter(main_formatter)
        axes[0, plot].set_ylabel("Price", color="green")
        prices = [trade.price for trade in trade_list]
        price_artist = axes[0, plot].plot(
                timestamps,
                prices,
                linewidth=0.8,
                label="Price",
                color="green",
                picker=8
            )

        # Create cursor for the price plot
        price_cursor = mplcursors.cursor(price_artist, hover=mplcursors.HoverMode.Transient)

        @price_cursor.connect("add")
        def on_add_price(sel):
            x, y = sel.target
            sel.annotation.set_text(f"Timestamp: {x}\nPrice: {y}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")

        # Plot the quantity data
        axes[1, plot].xaxis.set_major_formatter(main_formatter)
        axes[1, plot].yaxis.set_major_formatter(main_formatter)
        axes[1, plot].set_ylabel("Quantity", color="blue")
        quantities = [trade.quantity for trade in trade_list]
        quantity_artist = axes[1, plot].plot(
                timestamps,
                quantities,
                linewidth=0.8,
                label="Quantity",
                color="blue",
                picker=8
            )
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

        # Create cursor for the quantity plot
        quantity_cursor = mplcursors.cursor(quantity_artist, hover=mplcursors.HoverMode.Transient)

        @quantity_cursor.connect("add")
        def on_add_quantity(sel):
            x, y = sel.target
            sel.annotation.set_text(f"Timestamp: {x}\nQuantity: {y}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

        # Plot the price on the master plot
        ax_master.plot(timestamps, prices, label=symbol, picker=8)

    # Create master cursor
    master_cursor = mplcursors.cursor(ax_master, hover=mplcursors.HoverMode.Transient)

    @master_cursor.connect("add")
    def on_add_master(sel):
        x, y = sel.target
        sel.annotation.set_text(f"Item: {sel.artist.get_label()}\nTimestamp: {x}\nPrice: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    # Actually plot everything
    ax_master.legend()
    plt.tight_layout()
    plt.show()


class PriceData:
    def __init__(
            self,
            timestamp: int,
            product: str,
            bid_prices: list,
            bid_volumes: list,
            ask_prices: list,
            ask_volumes: list,
            ):
        self.timestamp = timestamp
        self.product = product
        self.bid_price = avg(bid_prices)
        self.ask_price = avg(ask_prices)
        self.bid_volume = avg(bid_volumes)
        self.ask_volume = avg(ask_volumes)

    def __lt__(self, other):
        return self.timestamp < other.timestamp


def analyze_price_data(data: pd.DataFrame, filename: str):
    # Dictionary mapping trade items to their data by timestamp
    prices = defaultdict(list)
    for _, row in data.iterrows():
        prices[row["product"]].append(PriceData(
            int(row["timestamp"]),  # type: ignore
            str(row["product"]),
            [row[f"bid_price_{i}"] for i in range(1, 4)],
            [row[f"bid_volume_{i}"] for i in range(1, 4)],
            [row[f"ask_price_{i}"] for i in range(1, 4)],
            [row[f"ask_volume_{i}"] for i in range(1, 4)]
        ))

    # Check if any data was loaded
    if not prices:
        print("No price data found for analysis")
        return

    # Sort each price item by timestamp
    for price_list in prices.values():
        price_list.sort()

    # Create a subplot for each price item
    # The first two rows show bid/ask and quantity data for each price item
    # The third row contain a master subplot of all the price items
    fig, axes = plt.subplots(3, len(prices.items()), figsize=(12, 6))
    fig.suptitle(f"Price Data Analysis for {filename}")
    for ax in axes[2]:
        ax.remove()
    ax_master = fig.add_subplot(3, 1, 3)

    # Create a main formatter applied to all axes
    main_formatter = lambda v, _: f"{int(v)}"

    # Set plot data for the master plot
    ax_master.xaxis.set_major_formatter(main_formatter)
    ax_master.yaxis.set_major_formatter(main_formatter)
    ax_master.set_title("All Price Items")
    ax_master_artists = []

    # Store the timestamps and prices globally for the master cursor
    # Store them as a mapping between the symbol and the list of timestamps and prices for that symbol, so we can show the correct data in the master cursor
    timestamps = defaultdict(list)
    bid_prices = defaultdict(list)
    ask_prices = defaultdict(list)

    # Render each individual price item in a subplot
    for plot, (symbol, price_list) in enumerate(prices.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)
        axes[1, plot].set_xlabel("Timestamp")
        timestamps[symbol] = [price.timestamp for price in price_list]
        range_mask = np.arange(0, len(timestamps[symbol]), 4)

        # Plot the bid/ask price data
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].xaxis.set_major_formatter(main_formatter)
        axes[0, plot].yaxis.set_major_formatter(main_formatter)
        axes[0, plot].set_ylabel("Bid/Ask Price", color="green")
        bid_prices[symbol] = [price.bid_price for price in price_list]
        ask_prices[symbol] = [price.ask_price for price in price_list]
        axes[0, plot].vlines(
                timestamps[symbol],
                bid_prices[symbol],
                ask_prices[symbol],
                linewidth=0.8,
                label="Bid/Ask Price",
                color="green"
            )
        price_artist = axes[0, plot].vlines(
                np.array(timestamps[symbol])[range_mask],
                np.array(bid_prices[symbol])[range_mask],
                np.array(ask_prices[symbol])[range_mask],
                linewidth=2,
                alpha=0.0,
                picker=8
            )
        axes[0, plot].tick_params(axis="y", labelcolor="green")

        # Create cursor for the price plot
        price_cursor = mplcursors.cursor(price_artist, hover=mplcursors.HoverMode.Transient)

        @price_cursor.connect("add")
        def on_add_price(
                sel,
                timestamps_=timestamps[symbol],
                bid_prices_=bid_prices[symbol],
                ask_prices_=ask_prices[symbol]
                ):
            i = sel.index[0]
            sel.annotation.set_text(f"Timestamp: {timestamps_[i]}\nBid Price: {bid_prices_[i]}\nAsk Price: {ask_prices_[i]}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")

        # Plot the quantity data
        axes[1, plot].xaxis.set_major_formatter(main_formatter)
        axes[1, plot].yaxis.set_major_formatter(main_formatter)
        axes[1, plot].set_ylabel("Bid/Ask Volume", color="blue")
        bid_volumes = [price.bid_volume for price in price_list]
        ask_volumes = [price.ask_volume for price in price_list]
        axes[1, plot].vlines(
                timestamps[symbol],
                bid_volumes,
                ask_volumes,
                linewidth=0.8,
                label="Bid/Ask Volume",
                color="blue",
                picker=8
            )
        quantity_artist = axes[1, plot].vlines(
                np.array(timestamps[symbol])[range_mask],
                np.array(bid_volumes)[range_mask],
                np.array(ask_volumes)[range_mask],
                linewidth=2,
                alpha=0.0,
                picker=8
            )
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

        # Create cursor for the quantity plot
        quantity_cursor = mplcursors.cursor(quantity_artist, hover=mplcursors.HoverMode.Transient)

        @quantity_cursor.connect("add")
        def on_add_quantity(sel, timestamps_=timestamps[symbol]):
            i = sel.index[0]
            sel.annotation.set_text(f"Timestamp: {timestamps_[i]}\nBid Volume: {bid_volumes[i]}\nAsk Volume: {ask_volumes[i]}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

        # Plot the bid/ask price on the master plot
        ax_master.vlines(
                timestamps[symbol],
                bid_prices[symbol],
                ask_prices[symbol],
                linewidth=0.8,
                label=symbol,
                picker=8
            )
        ax_master_artists.append(
                ax_master.vlines(
                    np.array(timestamps[symbol])[range_mask],
                    np.array(bid_prices[symbol])[range_mask],
                    np.array(ask_prices[symbol])[range_mask],
                    linewidth=2,
                    alpha=0.0,
                    label=symbol,
                    picker=8
                )
            )

    # Create master cursor
    master_cursor = mplcursors.cursor(ax_master_artists, hover=mplcursors.HoverMode.Transient)

    @master_cursor.connect("add")
    def on_add_master(sel):
        i = sel.index[0]
        label = sel.artist.get_label()
        sel.annotation.set_text(f"Item: {label}\nTimestamp: {timestamps[label][i]}\nBid Price: {bid_prices[label][i]}\nAsk Price: {ask_prices[label][i]}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightyellow")

    ax_master.legend()
    plt.tight_layout()
    plt.show()


def analyze_data(file_path: str):
    # Load the csv data
    data = pd.read_csv(file_path, sep=";")

    # Analyze the data according to type
    if "buyer" in data.columns:
        analyze_trade_data(data, os.path.basename(file_path))
    elif "profit_and_loss" in data.columns:
        analyze_price_data(data, os.path.basename(file_path))
    else:
        print("Unknown data being analyzed")


# -- CLI ----------------------------------------------------------------------

def main():
    files = []
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            files.append(arg)
        else:
            print(f"Unknown argument: {arg}")
            return

    if not files:
        print("No files provided for analysis")
        return

    for file in files:
        analyze_data(file)


if __name__ == "__main__":
    main()
