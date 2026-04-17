"""Classifies trading bots based on their behavior and characteristics.
"""
from collections import defaultdict
import re

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import Voronoi, voronoi_plot_2d
import mplcursors

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


# -- PRIVATE HELPERS ----------------------------------------------------------

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
    day_regex = re.compile(r"(?<=day_)[-\d]{1,2}")

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

    trade_dataframes = dict(sorted(trade_dataframes.items()))
    price_dataframes = dict(sorted(price_dataframes.items()))

    # Timesteps are ~1 million per day, so concatenate dataframes for each day
    # and then concatenate all days.
    # Add 1 million for each day to the timestamp to ensure unique timestamps
    # across days.
    # Since trades and prices should have the same days, we can also check that
    # the same days are present in both dictionaries.
    trade_master = pd.DataFrame()
    price_master = pd.DataFrame()
    for i, day in enumerate(trade_dataframes.keys()):
        if day not in price_dataframes:
            print(f"Error: Day {day} is present in trade dataframes but not "
                  "price dataframes")
            return None

        trade_dataframes[day]["timestamp"] += i * 1_000_000
        trade_master = pd.concat(
                [trade_master, trade_dataframes[day]],
                ignore_index=True
                )
        price_dataframes[day]["timestamp"] += i * 1_000_000
        price_master = pd.concat(
                [price_master, price_dataframes[day]],
                ignore_index=True
                )

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
    final_dataframe = pd.DataFrame()
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
            midprice_open = curr.iloc[0]["mid_price"]  # type: ignore
            midprice_close = curr.iloc[-1]["mid_price"]  # type: ignore
            midprice_low = curr["mid_price"].min()
            midprice_high = curr["mid_price"].max()
            avg_trade_size = curr["quantity"].mean()
            final_dataframe = pd.concat(
                [
                    final_dataframe,
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
                        "num_trades": len(curr["quantity"]),  # Trade exclusive
                        "avg_trade_size": avg_trade_size if pd.notna(avg_trade_size) else 0  # type: ignore
                    }, index=["timestamp_start"]),
                    ],
                ignore_index=True
                )

    return final_dataframe.set_index("timestamp_start")


def classify_bots(data: pd.DataFrame, clusters: int) -> None:
    """Classify trading bots based on their behavior and characteristics.

    Uses k-means clustering to group bots into distinct categories based on
    their trading patterns and features.

    Args:
        data: DataFrame containing the trading data for classification.
        clusters: The number of clusters to use for classification.

    Returns:
        None.
    """
    # Drop columns for timesteps
    dropped = data.drop(
            columns=["timestamp_start", "timestamp_end"],
            errors="ignore"
            )
    # Perform 1-hot encoding for purchased items
    features = pd.get_dummies(dropped, columns=["symbol"], drop_first=True)
    # Normalize the features and perform PCA for dimensionality reduction
    scaler = StandardScaler()
    pca = PCA(n_components=2, svd_solver="full")
    pca_features = pca.fit_transform(scaler.fit_transform(features))
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=clusters, random_state=0)
    kmeans.fit(pca_features)

    # Plot the clusters in a Voronoi diagram
    fig = plt.figure(figsize=(16, 8))
    axes = fig.add_subplot(1, 1, 1)
    fig.subplots_adjust(right=0.8, bottom=0.2, top=0.8)

    colormap = plt.get_cmap("viridis", clusters)
    scatter = axes.scatter(
            pca_features[:, 0],
            pca_features[:, 1],
            c=kmeans.labels_,
            cmap=colormap,
            edgecolor='k',
            alpha=0.6,
            s=10,
            picker=8
            )
    voronoi = Voronoi(kmeans.cluster_centers_)
    fig = voronoi_plot_2d(
            voronoi,
            ax=axes,
            show_vertices=False,
            show_points=False,
            line_colors='k',
            line_width=1,
            )
    axes.set_xlabel("PCA Component 1")
    axes.set_ylabel("PCA Component 2")
    axes.set_title("K-Means Clustering of Trading Bots")

    # Create cursor for hover annotations
    COL_NAMES = {
        "symbol": "Symbol",
        "symbol_INTARIAN_PEPPER_ROOT": "Symbol",
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
    cursor = mplcursors.cursor(scatter, hover=mplcursors.HoverMode.Transient)

    # TODO: Add descriptions showing composition of PCA axes
    contributions = np.square(pca.components_)
    contributions = contributions / contributions.sum(axis=1, keepdims=True)
    contributions_dataframe = pd.DataFrame(
            contributions * 100,
            columns=features.columns
            )
    fig.text(
        0.82,
        0.55,
        "PCA Component 1 Composition:\n\n" +
        '\n'.join(f"{COL_NAMES.get(col, col)}: {contributions_dataframe[col].iloc[0]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightblue", alpha=0.5, boxstyle="round"),
        )
    fig.text(
        0.82,
        0.225,
        "PCA Component 2 Composition:\n\n" +
        '\n'.join(f"{COL_NAMES.get(col, col)}: {contributions_dataframe[col].iloc[1]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightgreen", alpha=0.5, boxstyle="round"),
        )

    @cursor.connect("add")
    def on_add(sel):
        index = sel.index

        local_data = data.iloc[[index]]
        numeric_columns = local_data.select_dtypes(include='number').columns
        local_data[numeric_columns] = local_data[numeric_columns].round(4)
        sel.annotation.set_text(
            f"Start Timestamp: {local_data.index[0]}\n" +
            '\n'.join(f"{COL_NAMES.get(col, col)}: {local_data[col].iloc[0]}" for col in dropped.columns) +
            f"\nCluster: {kmeans.labels_[index]}"  # type: ignore
            )
        sel.annotation.get_bbox_patch().set_alpha(0.95)
        sel.annotation.get_bbox_patch().set_facecolor(
            colormap(kmeans.labels_[index])  # type: ignore
            )

    # Actually plot the clusters
    plt.show()
