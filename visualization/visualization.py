import sys
import os
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt


# -- HELPER FUNCTIONS ---------------------------------------------------------

# Checks if a value can be cast to a given type
def castable(value, to_type):
    try:
        to_type(value)
        return True
    except ValueError:
        return False


def avg(values: list):
    actual = list(filter(lambda v: pd.notna(v) and castable(v, float), values))
    return sum(map(float, actual)) / len(actual) if actual else 0


# -- ANALYSIS FUNCTIONS -------------------------------------------------------

class TradeData:
    def __init__(
            self,
            timestamp: int,
            trade_type: str,
            quantity: int,
            price: float
            ):
        self.timestamp = timestamp
        self.trade_type = trade_type
        self.quantity = quantity
        self.price = price

    def __lt__(self, other):
        return self.timestamp < other.timestamp


# TODO: Add functionality to display the trades as an iterative animation
def analyze_trade_data(data: pd.DataFrame, filename: str):
    # Dictionary mapping trade items to their data by timestamp
    trades = defaultdict(list[TradeData])
    for _, row in data.iterrows():
        trades[row["symbol"]].append(TradeData(
            int(row["timestamp"]),  # type: ignore
            str(row["symbol"]),
            int((row["quantity"])),  # type: ignore
            float(row["price"])  # type: ignore
        ))

    # Create a subplot for each trade item
    # The first two rows show price and quantity data for each trade item
    # The third row contain a master subplot of all the trade items
    fig, axes = plt.subplots(3, len(trades.items()), figsize=(12, 6))
    fig.suptitle(f"Trade Data Analysis for {filename}")
    for ax in axes[2]:
        ax.remove()
    ax_master = fig.add_subplot(3, 1, 3)

    # Set plot data for the master plot
    ax_master.xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
    ax_master.yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
    ax_master.set_title("All Trade Items")

    # Render each individual trade item in a subplot
    for plot, (symbol, trade_queue) in enumerate(trades.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)
        axes[1, plot].set_xlabel("Timestamp")
        timestamps = [trade.timestamp for trade in trade_queue]

        # Plot the trade data
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
        axes[0, plot].yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
        axes[0, plot].set_ylabel("Price", color="green")
        prices = [trade.price for trade in trade_queue]
        axes[0, plot].plot(timestamps, prices, linewidth=0.8, label="Price", color="green")

        # Plot the quantity data
        axes[1, plot].xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
        axes[1, plot].yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
        axes[1, plot].set_ylabel("Quantity", color="blue")
        quantities = [trade.quantity for trade in trade_queue]
        axes[1, plot].plot(timestamps, quantities, linewidth=0.8, label="Quantity", color="blue")
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

        # Plot the price on the master plot
        ax_master.plot(timestamps, prices, label=symbol)

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
    prices = defaultdict(list[PriceData])
    for _, row in data.iterrows():
        prices[row["product"]].append(PriceData(
            int(row["timestamp"]),  # type: ignore
            str(row["product"]),
            [row[f"bid_price_{i}"] for i in range(1, 4)],
            [row[f"bid_volume_{i}"] for i in range(1, 4)],
            [row[f"ask_price_{i}"] for i in range(1, 4)],
            [row[f"ask_volume_{i}"] for i in range(1, 4)]
        ))

    # Create a subplot for each price item
    # The first two rows show bid/ask and quantity data for each price item
    # The third row contain a master subplot of all the price items
    fig, axes = plt.subplots(3, len(prices.items()), figsize=(12, 6))
    fig.suptitle(f"Price Data Analysis for {filename}")
    for ax in axes[2]:
        ax.remove()
    ax_master = fig.add_subplot(3, 1, 3)

    # Set plot data for the master plot
    ax_master.xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
    ax_master.yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
    ax_master.set_title("All Price Items")

    # Render each indivudal price item in a subplot
    for plot, (symbol, price_queue) in enumerate(prices.items()):
        # Set shared axis data
        axes[0, plot].set_title(symbol)
        axes[1, plot].set_xlabel("Timestamp")
        timestamps = [price.timestamp for price in price_queue]

        # Plot the bid/ask price data
        axes[0, plot].tick_params(axis="y", labelcolor="green")
        axes[0, plot].xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
        axes[0, plot].yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
        axes[0, plot].set_ylabel("Bid/Ask Price", color="green")
        bid_prices = [price.bid_price for price in price_queue]
        ask_prices = [price.ask_price for price in price_queue]
        axes[0, plot].vlines(timestamps, bid_prices, ask_prices, linewidth=0.8, label="Bid/Ask Price", color="green")
        axes[0, plot].tick_params(axis="y", labelcolor="green")

        # Plot the quantity data
        axes[1, plot].xaxis.set_major_formatter(lambda x, _: f"{int(x)}")
        axes[1, plot].yaxis.set_major_formatter(lambda y, _: f"{int(y)}")
        axes[1, plot].set_ylabel("Bid/Ask Volume", color="blue")
        bid_volumes = [price.bid_volume for price in price_queue]
        ask_volumes = [price.ask_volume for price in price_queue]
        axes[1, plot].vlines(timestamps, bid_volumes, ask_volumes, linewidth=0.8, label="Bid/Ask Volume", color="blue")
        axes[1, plot].tick_params(axis="y", labelcolor="blue")

        # Plot the bid/ask price on the master plot
        ax_master.vlines(timestamps, bid_prices, ask_prices, linewidth=0.8, label=symbol)

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
