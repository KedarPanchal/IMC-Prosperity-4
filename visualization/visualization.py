import sys
import math
from heapq import heapify, heappop
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt


class TradeData:
    def __init__(self, timestamp: int, trade_type: str, quantity: int, price: float):
        self.timestamp = timestamp
        self.trade_type = trade_type
        self.quantity = quantity
        self.price = price

    def __lt__(self, other):
        return self.timestamp < other.timestamp


def analyze_trade_data(data: pd.DataFrame):
    # Dictionary mapping trade items to priority queue by timestamp
    trades = defaultdict(list)
    for _, row in data.iterrows():
        trades[row["symbol"]].append(TradeData(
            int(row["timestamp"]),  # type: ignore
            str(row["symbol"]),
            int((row["quantity"])),  # type: ignore
            float(row["price"])  # type: ignore
        ))

    # Convert the lists of trades into priority queues
    for symbol in trades:
        heapify(trades[symbol])

    # The plot will contain a subplot for each trade item
    # Compute rows and columns for the plot
    # Round down for rows and round up for columns
    rows = int(len(trades) ** 0.5)
    cols = math.ceil(len(trades) / rows)

    fig, axes = plt.subplots(rows, cols, figsize=(9, 6), sharex=True)
    for ax, (symbol, trade_queue) in zip(axes.flatten(), trades.items()):
        # TODO: For now we just plot the price, but also plot the quantity
        timestamps = [trade.timestamp for trade in trade_queue]
        prices = [trade.price for trade in trade_queue]
        ax.plot(timestamps, prices)

    plt.tight_layout()
    plt.show()



def analyze_price_data(data: pd.DataFrame):
    pass


def analyze_data(file_path: str):
    # Load the csv data
    data = pd.read_csv(file_path, sep=";")

    # Analyze the data according to type
    if "buyer" in data.columns:
        analyze_trade_data(data)
    elif "profit_and_loss" in data.columns:
        analyze_price_data(data)
    else:
        print("Unknown data being analyzed")


def main():
    for file_path in sys.argv[1:]:
        analyze_data(file_path)


if __name__ == "__main__":
    main()
