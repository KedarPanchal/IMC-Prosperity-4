"""Classifies trading bots based on their behavior and characteristics.
"""
from collections import defaultdict
import re

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.widgets as widgets
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import mplcursors
from scipy.spatial import Voronoi, voronoi_plot_2d

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


# -- PRIVATE HELPERS ----------------------------------------------------------

def _make_plot():
    """Create a figure with a grid layout for the trading bot classification 
    visualization.
    """
    fig = plt.figure(figsize=(16, 8))
    gs = gridspec.GridSpec(
        nrows=1,
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
        fig.canvas.manager.set_window_title("Trading Bot Classification")  # type: ignore
    except AttributeError:
        print("Warning: Unable to set window title; feature may be unsupported in this environment")

    fig.suptitle("Trading Bot Classification")

    control_axes = fig.add_subplot(gs[0, 0])
    control_axes.set_xticks([])
    control_axes.set_yticks([])
    control_axes.set_frame_on(False)

    data_axes = fig.add_subplot(gs[0, 1])

    return fig, data_axes, control_axes


def _plot_data(data_axes: Axes, data: np.ndarray, k: int, seed: int):
    """Plot the trading bot data using k-means clustering and Voronoi diagrams.

    Args:
        data_axes: The axes to plot the data on.
        data: The PCA-transformed data to plot.
        k: The number of clusters to use for k-means clustering.
        seed: The random seed to use for k-means clustering.
    Returns:
        The fitted KMeans model, the scatter plot object, and the colormap used
        for plotting.
    """
    kmeans = KMeans(n_clusters=k, random_state=seed)
    kmeans.fit(data)
    data_axes.clear()

    colormap = plt.get_cmap("viridis", k)
    scatter = data_axes.scatter(
            data[:, 0],
            data[:, 1],
            c=kmeans.labels_,
            cmap=colormap,
            edgecolor='k',
            alpha=0.6,
            s=10,
            picker=8
            )
    data_axes.set_xlabel("PCA Component 1")
    data_axes.set_ylabel("PCA Component 2")
    data_axes.set_title(f"K-Means Clustering of Trading Bots (k={k}, seed={seed})")
    if len(kmeans.cluster_centers_) >= 2:
        voronoi = Voronoi(kmeans.cluster_centers_)
        voronoi_plot_2d(
                voronoi,
                ax=data_axes,
                show_vertices=False,
                show_points=False,
                line_colors='k',
                line_width=1,
                )
    return kmeans, scatter, colormap


def _kmeans_gui(fig: Figure, data: np.ndarray, control_axes: Axes, data_axes: Axes):
    """Create a GUI for adjusting the number of clusters (k) and random seed
    for k-means clustering.

    Args:
        fig: The figure to add the GUI to.
        data: The PCA-transformed data to plot.
        control_axes: The axes to add the GUI controls to.
        data_axes: The axes to update with the new clustering results when the
        controls are adjusted.

    Returns:
        The TextBox widgets for k and random seed since matplotlib requires
        keeping references to them to prevent garbage collection.
    """
    k_axes = control_axes.inset_axes((0.6, 0.95, 0.42, 0.04))
    k_label = widgets.TextBox(
        k_axes,
        label="Number of Clusters (k): ",
        initial="10"
        )
    seed_axes = control_axes.inset_axes((0.4, 0.9, 0.62, 0.04))
    seed_label = widgets.TextBox(
        seed_axes,
        label="Random Seed: ",
        initial="0"
        )

    def change_kmeans(label):
        try:
            k = int(k_label.text)
            seed = int(seed_label.text)
            if k <= 0:
                print("Warning: Number of clusters must be positive, defaulting to 10")
                k = 10
            if seed < 0:
                print("Warning: Random seed must be non-negative, defaulting to 0")
                seed = 0
        except ValueError:
            print("Warning: Invalid input for k or random seed, defaulting to k=10 and seed=0")
            k = 10
            seed = 0

        _plot_data(data_axes, data, k, seed)
        fig.canvas.draw_idle()

    k_label.on_submit(change_kmeans)
    seed_label.on_submit(change_kmeans)

    return k_label, seed_label


def _pca_contributions(pca: PCA, features: pd.DataFrame, control_axes: Axes):
    contributions = np.square(pca.components_)
    contributions = contributions / contributions.sum(axis=1, keepdims=True)
    contributions_dataframe = pd.DataFrame(
            contributions * 100,
            columns=features.columns
            )
    pca1_text = control_axes.text(
        0.05,
        0.85,
        "PCA Component 1 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[0]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightblue", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=8
        )
    pca2_text = control_axes.text(
        0.05,
        0.40,
        "PCA Component 2 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[1]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightgreen", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=8
        )
    return pca1_text, pca2_text


# -- MAIN LOGIC ---------------------------------------------------------------

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


def classify_bots(data: pd.DataFrame) -> None:
    """Classify trading bots based on their behavior and characteristics.

    Uses k-means clustering to group bots into distinct categories based on
    their trading patterns and features.

    Args:
        data: DataFrame containing the trading data for classification.

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

    # Perform k means clustering and plot the results
    fig, axes, control_axes = _make_plot()
    kmeans, scatter, colormap = _plot_data(axes, pca_features, 10, seed=0)

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

    # Show the GUI for adjusting k and random seed
    # Also show the PCA component contributions
    _ = _kmeans_gui(fig, pca_features, control_axes, axes)
    _pca_contributions(pca, features, control_axes)
    # Actually plot the clusters
    plt.show()
