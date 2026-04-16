"""Classifies trading bots based on their behavior and characteristics.
"""
from collections import defaultdict
import re

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplcursors

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# -- PRIVATE HELPERS ----------------------------------------------------------

def _pca(N: np.ndarray, d: int) -> np.ndarray:
    """Perform Principal Component Analysis (PCA) on a dataset to produce its
    d-dimensional projection.

    Args:
        n: A numpy array representing the dataset to be reduced.
        d: The target dimensionality for the PCA projection (e.g., 2 for 2D).
        Assumed to be less than or equal to the original dimensionality.

    Returns:
        A k x d numpy array containing the projection of the original data onto
        the first two principal components, where k is the number of samples in
        the original dataset.
    """
    # Center the data
    N = N - np.mean(N, axis=0)
    C = np.cov(N, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(C)
    # Sort eigenvalues and eigenvectors in descending order
    idx = np.argsort(eigenvalues)[::-1]
    eigenvectors = eigenvectors[:, idx]
    # Project the data onto the first two principal components
    return eigenvectors[:, :d]


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
        trade_master = trade_master.append(
                trade_dataframes[day],
                ignore_index=True
                )
        price_dataframes[day]["timestamp"] += i * 1_000_000
        price_master = price_master.concat(
                price_dataframes[day],
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
    final_timestep = master["timestamp"].max()

    # Timesteps have a difference of about 2k between them
    # This means in the final dataframe, aggregate data in steps of 2k
    final_dataframe = pd.DataFrame()
    for i in range(0, final_timestep + 1, 2000):
        timestamped = master[
                (master["timestamp"] >= i) & (master["timestamp"] < i + 2000)
                ]
        cols = [
                "bid_price_1",
                "bid_price_2",
                "bid_price_3",
                "ask_price_1",
                "ask_price_2",
                "ask_price_3"
                ]
        # Compute metrics for every symbol in the current timestep
        for symbol in set(timestamped["symbol"]):
            curr = timestamped[timestamped["symbol"] == symbol]
            midprice_open = curr.iloc[0][cols].mean(axis=1)  # type: ignore
            midprice_close = curr.iloc[-1][cols].mean(axis=1)  # type: ignore
            midprice_low = curr[cols].mean(axis=1).min()
            midprice_high = curr[cols].mean(axis=1).max()
            final_dataframe = final_dataframe.append(
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
                    "avg_trade_size": curr["quantity"].mean(),
                    }),
                ignore_index=True
                )

        return final_dataframe


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
    features = data.drop(
            columns=["timestamp_start", "timestep_end"],
            errors="ignore"
            )
    # Perform 1-hot encoding for purchased items
    features = pd.get_dummies(features, columns=["symbol"], drop_first=True)
    # Normalize the features
    scaler = StandardScaler()
    pca_features = _pca(scaler.fit_transform(features.to_numpy()), 2)
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=clusters, random_state=0)
    kmeans.fit(pca_features)

    # Plot the clusters in 3D, since their dimension is 3D anyway
    fig = plt.figure(figsize=(16, 8))
    axes = fig.add_subplot(1, 1, 1)
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
    axes.set_xlabel("PCA Component 1")
    axes.set_ylabel("PCA Component 2")
    axes.set_title("K-Means Clustering of Trading Bots")

    # Extract relevant features for hover annotations
    hover_data = data[["timestamp", "symbol"]].to_numpy()

    # Create cursor for hover annotations
    cursor = mplcursors.cursor(scatter, hover=mplcursors.HoverMode.Transient)

    @cursor.connect("add")
    def on_add(sel):
        index = sel.index
        timestamp, symbol = hover_data[index]
        sel.annotation.set_text(f"Timestamp: {timestamp}\nSymbol: {symbol}\nCluster: {kmeans.labels_[index]}")  # type: ignore
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor(
            colormap(kmeans.labels_[index])  # type: ignore
            )

    # Actually plot the clusters
    fig.colorbar(scatter, ax=axes, label="Cluster Label")
    plt.show()
