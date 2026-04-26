"""Internal functions shared by machine learning modes.
"""

from collections import defaultdict
import re

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.axes import Axes

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


# -- PLOTTING -----------------------------------------------------------------

def make_plot(title: str, rows: int):
    """Create a figure with a grid layout for an ML
    visualization.

    Args:
        title: The title of the plot.
        rows: The number of rows in the grid layout (number of data subplots).

    Returns:
        A tuple containing the figure, a list of data axes, and the control 
        axes.
    """
    fig = plt.figure(figsize=(16, 8))
    gs = gridspec.GridSpec(
        nrows=rows,
        ncols=2,
        figure=fig,
        left=0.05,
        right=0.95,
        top=0.95,
        bottom=0.1,
        wspace=0.25,
        hspace=0.5,
        width_ratios=[1, 3],
        )
    try:
        fig.canvas.manager.set_window_title(title)  # type: ignore
    except AttributeError:
        print("Warning: Unable to set window title; feature may be unsupported in this environment")

    fig.suptitle(title)

    control_axes = fig.add_subplot(gs[:, 0])
    control_axes.set_xticks([])
    control_axes.set_yticks([])
    control_axes.set_frame_on(False)

    data_axes = []
    for r in range(rows):
        data_axes.append(fig.add_subplot(gs[r, 1]))

    return fig, data_axes, control_axes


def pca_contributions(pca: PCA, features: pd.DataFrame, control_axes: Axes):
    contributions = np.square(pca.components_)
    contributions = contributions / contributions.sum(axis=1, keepdims=True)
    contributions_dataframe = pd.DataFrame(
            contributions * 100,
            columns=features.columns
            )
    pca1_text = control_axes.text(
        0.05,
        0.75,
        "PCA Component 1 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[0]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightblue", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=8
        )
    pca2_text = control_axes.text(
        0.05,
        0.35,
        "PCA Component 2 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[1]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightgreen", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=8
        )
    return pca1_text, pca2_text


# -- DATA PREPARATION --------------------------------------------------------

def collate_data(files: list[str]) -> pd.DataFrame | None:
    """Collate data from multiple files into a single dataset for
    classification.

    Combines data from the provided files, ensuring that only valid dataframes
    for trading bot classification are included.

    Args:
        files: List of file paths to collate data from.

    Returns:
        A single DataFrame containing the collated data from all valid files.
    """
    # Split dataframes into trade and price dataframes by day
    trade_dataframes = defaultdict(pd.DataFrame)
    price_dataframes = defaultdict(pd.DataFrame)
    day_regex = re.compile(r"(?<=day_)-?\d+")

    for file in files:
        df = pd.read_csv(file, sep=';')
        match = day_regex.search(file)
        if not match:
            print(f"Warning: File {file} does not contain a valid day number")
            continue
        day = int(match.group())
        if "trades" in file:
            trade_dataframes[day] = df
        elif "prices" in file:
            price_dataframes[day] = df
        else:
            print(
                f"Warning: File {file} is not a valid trade or price "
                "dataframe"
                )

    # Exit early if the same number of trade and price rows haven't been read
    if len(trade_dataframes) != len(price_dataframes):
        print(
            f"Error: Processed {len(trade_dataframes)} trade dataframes but "
            f"only {len(price_dataframes)} price dataframes"
            )
        return None

    if len(trade_dataframes) == 0:
        print("Error: No valid trade or price dataframes to process")
        return None

    trade_dataframes = dict(sorted(trade_dataframes.items()))
    price_dataframes = dict(sorted(price_dataframes.items()))

    # Timesteps are ~1 million per day, so concatenate dataframes for each day
    # and then concatenate all days.
    # Add 1 million for each day to the timestamp to ensure unique timestamps
    # across days.
    # Since trades and prices should have the same days, we can also check that
    # the same days are present in both dictionaries.
    trade_master_list = []
    price_master_list = []
    for i, day in enumerate(trade_dataframes.keys()):
        if day not in price_dataframes:
            print(f"Error: Day {day} is present in trade dataframes but not "
                  "price dataframes")
            return None

        trade_dataframes[day]["timestamp"] += i * 1_000_000
        trade_master_list.append(trade_dataframes[day])
        price_dataframes[day]["timestamp"] += i * 1_000_000
        price_master_list.append(price_dataframes[day])

    trade_master = pd.concat(trade_master_list, ignore_index=True)
    price_master = pd.concat(price_master_list, ignore_index=True)

    # Aggregate data by timestep and symbol as an outer join to ensure all
    # timesteps are included, even if they only appear in one of the
    # dataframes.
    price_master.rename(columns={"product": "symbol"}, inplace=True)
    master = pd.merge(
            trade_master,
            price_master,
            on=["timestamp", "symbol"],
            how="outer"
            )
    final_timestep = int(master["timestamp"].max())  # type: ignore

    # Timesteps have a difference of about 2k between them
    # This means in the final dataframe, aggregate data in steps of 2k
    final_dataframe_components = []
    for i in range(0, final_timestep + 1, 2000):
        timestamped = master[
                (master["timestamp"] >= i) & (master["timestamp"] < i + 2000)
                ]
        # Compute metrics for every symbol in the current timestep
        for symbol in set(timestamped["symbol"]):
            # A mid_price of 0 means no trades occurred
            curr = timestamped[
                    (timestamped["symbol"] == symbol) &
                    (timestamped["mid_price"] > 0)
                    ]
            if curr.empty:  # type: ignore
                continue

            midprice_open = curr.iloc[0]["mid_price"]  # type: ignore
            midprice_close = curr.iloc[-1]["mid_price"]  # type: ignore
            midprice_low = curr["mid_price"].min()
            midprice_high = curr["mid_price"].max()
            avg_trade_size = curr.loc[curr["quantity"] > 0, "quantity"].mean()  # type: ignore
            final_dataframe_components.append(
                    pd.DataFrame({
                        "timestamp_start": i,
                        "timestamp_end": i + 1999,  # Inclusive end timestamp
                        "symbol": symbol,
                        "midprice_open": midprice_open,
                        "midprice_close": midprice_close,
                        "midprice_low": midprice_low,
                        "midprice_high": midprice_high,
                        "midprice_return": midprice_close / midprice_open - 1,
                        "midprice_range": midprice_high - midprice_low,
                        "total_volume": curr["quantity"].sum(),
                        "num_trades": len(curr.loc[curr["quantity"] > 0, "quantity"]),  # type: ignore
                        "avg_trade_size": avg_trade_size if pd.notna(avg_trade_size) else 0  # type: ignore
                    }, index=["timestamp_start"]),
                )

    final_dataframe = pd.concat(final_dataframe_components, ignore_index=True)
    return final_dataframe.set_index("timestamp_start")


def preprocess_data(data: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Preprocess the data for machine learning by performing feature
    engineering and normalization.

    Args:
        data: DataFrame containing the raw trading data to preprocess.

    Returns:
        A tuple containing the following elements:
        - A DataFrame with the original data (with timestamp columns dropped).
        - A DataFrame with the engineered features (after 1-hot encoding).
        - A NumPy array containing the normalized feature values.
    """
    # Drop columns for timesteps
    dropped = data.drop(
        columns=["timestamp_start", "timestamp_end"],
        errors="ignore"
        )
    # Perform 1-hot encoding for purchased items
    features = pd.get_dummies(dropped, columns=["symbol"], drop_first=True)
    # Normalize the features
    scaler = StandardScaler()
    return features, scaler.fit_transform(features)


# -- GLOBAL CONSTANTS ---------------------------------------------------------

COL_NAMES = {
    "symbol": "Symbol",
    "midprice_open": "Mid Price Open",
    "midprice_close": "Mid Price Close",
    "midprice_low": "Mid Price Low",
    "midprice_high": "Mid Price High",
    "midprice_return": "Mid Price Return",
    "midprice_range": "Mid Price Range",
    "total_volume": "Total Volume",
    "num_trades": "Number of Trades",
    "avg_trade_size": "Average Trade Size",
}
