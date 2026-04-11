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
    fig, axes = plt.subplots(3, len(trades.items()), figsize=(16, 8))
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

    # Create arrays to store each artist for rendering the cursors
    price_artists = []
    quantity_artists = []
    master_artists = []

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
        price_artists.extend(
                axes[0, plot].plot(
                    timestamps,
                    prices,
                    linewidth=0.8,
                    label="Price",
                    color="green",
                    picker=8
                )
            )

        # Plot the quantity data
        axes[1, plot].xaxis.set_major_formatter(main_formatter)
        axes[1, plot].yaxis.set_major_formatter(main_formatter)
        axes[1, plot].set_ylabel("Quantity", color="blue")
        quantities = [trade.quantity for trade in trade_list]
        quantity_artists.extend(
                axes[1, plot].plot(
                    timestamps,
                    quantities,
                    linewidth=0.8,
                    label="Quantity",
                    color="blue",
                    picker=8
                )
            )
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

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
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nPrice: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightgreen")

    # Create cursor for the quantity plot
    quantity_cursor = mplcursors.cursor(quantity_artists, hover=mplcursors.HoverMode.Transient)

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
        x, y = sel.target
        sel.annotation.set_text(f"Timestamp: {x}\nQuantity: {y}")
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor("lightblue")

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
    # The third row contains a master subplot of all the price items
    fig, axes = plt.subplots(4, len(prices.items()), figsize=(16, 8))
    fig.suptitle(f"Price Data Analysis for {filename}")
    for ax in axes[3]:
        ax.remove()
    ax_master = fig.add_subplot(4, 1, 4)

    # Create a main formatter applied to all axes
    main_formatter = lambda v, _: f"{int(v)}"

    # Set plot data for the master plot
    ax_master.xaxis.set_major_formatter(main_formatter)
    ax_master.yaxis.set_major_formatter(main_formatter)
    ax_master.set_title("All Price Items")

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
        axes[0, plot].set_title(symbol)
        axes[2, plot].set_xlabel("Timestamp")
        timestamps = [price.timestamp for price in price_list]

        # Plot the bid/ask price data
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].xaxis.set_major_formatter(main_formatter)
        axes[0, plot].yaxis.set_major_formatter(main_formatter)
        axes[0, plot].set_ylabel("Bid/Ask Price", color="green")
        bid_prices = [price.bid_price for price in price_list]
        ask_prices = [price.ask_price for price in price_list]
        fair_value_prices = [(bid + ask) / 2 for bid, ask in zip(bid_prices, ask_prices)]
        bid_price_artists.extend(
                axes[0, plot].plot(
                    timestamps,
                    bid_prices,
                    linewidth=0.8,
                    label="bid",
                    color="green"
                )
            )
        ask_price_artists.extend(
                axes[0, plot].plot(
                    timestamps,
                    ask_prices,
                    linewidth=0.8,
                    label="ask",
                    color="red"
                )
            )
        fair_value_artists.extend(
                axes[0, plot].plot(
                    timestamps,
                    fair_value_prices,
                    linewidth=0.8,
                    label="fair value",
                    color="blue"
                )
            )
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].legend()

        # Plot the bid quantity data
        axes[1, plot].xaxis.set_major_formatter(main_formatter)
        axes[1, plot].yaxis.set_major_formatter(main_formatter)
        axes[1, plot].set_ylabel("Bid Volume", color="blue")
        bid_volumes = [price.bid_volume for price in price_list]
        bid_quantity_artists.extend(
                axes[1, plot].plot(
                    timestamps,
                    bid_volumes,
                    linewidth=0.8,
                    label="bid",
                    color="blue",
                    picker=8
                )
            )
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

        # Plot the ask quantity data
        axes[2, plot].xaxis.set_major_formatter(main_formatter)
        axes[2, plot].yaxis.set_major_formatter(main_formatter)
        axes[2, plot].set_ylabel("Ask Volume", color="orange")
        ask_volumes = [price.ask_volume for price in price_list]
        ask_quantity_artists.extend(
                axes[2, plot].plot(
                    timestamps,
                    ask_volumes,
                    linewidth=0.8,
                    label="ask",
                    color="orange",
                    picker=8
                )
            )
        axes[2, plot].tick_params(axis="y", labelcolor="orange")

        # Plot the bid/ask price on the master plot
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
    quantity_cursor = mplcursors.cursor([*bid_quantity_artists, *ask_quantity_artists], hover=mplcursors.HoverMode.Transient)

    @quantity_cursor.connect("add")
    def on_add_quantity(sel):
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
    master_cursor = mplcursors.cursor([*bid_master_artists, *ask_master_artists, *fair_value_master_artists], hover=mplcursors.HoverMode.Transient)

    @master_cursor.connect("add")
    def on_add_master(sel):
        x, y = sel.target
        symbol, type = sel.artist.get_label().split()
        if type == "bid":
            sel.annotation.set_text(f"Item: {symbol} bid\nTimestamp: {int(x)}\nBid Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightgreen")
        elif type == "ask":
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nAsk Price: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightcoral")
        else:
            sel.annotation.set_text(f"Item: {symbol}\nTimestamp: {int(x)}\nFair Value: {float(y):.2f}")
            sel.annotation.get_bbox_patch().set_alpha(0.9)
            sel.annotation.get_bbox_patch().set_facecolor("lightblue")

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
