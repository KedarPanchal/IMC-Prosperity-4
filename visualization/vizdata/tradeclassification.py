"""Classifies trading data based on their behavior and characteristics.
"""

from collections import defaultdict
import re

import pandas as pd
import numpy as np

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from scipy.spatial import Voronoi, voronoi_plot_2d

import matplotlib.pyplot as plt
import matplotlib.widgets as widgets
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import mplcursors

from .mlutils import make_plot


# -- DATA PROCESSING HELPERS --------------------------------------------------
def _collate_data(files: list[str]) -> pd.DataFrame | None:
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
    try:
        final_dataframe = pd.concat(final_dataframe_components, ignore_index=True)
        return final_dataframe.set_index("timestamp_start")
    except ValueError:
        print("Error: No valid data to process after aggregation")
        return None


def _preprocess_data(data: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Preprocess the data for machine learning by performing feature
    engineering and normalization.

    Args:
        data: DataFrame containing the raw trading data to preprocess.

    Returns:
        A tuple containing the following elements:
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


# -- PLOTTING HELPERS ---------------------------------------------------------

def _pca_contributions(pca: PCA, features: pd.DataFrame, control_axes: Axes):
    contributions = np.square(pca.components_)
    contributions = contributions / contributions.sum(axis=1, keepdims=True)
    contributions_dataframe = pd.DataFrame(
            contributions * 100,
            columns=features.columns
            )
    pca1_text = control_axes.text(
        0.05,
        0.68,
        "PCA Component 1 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[0]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightblue", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=7
        )
    pca2_text = control_axes.text(
        0.05,
        0.28,
        "PCA Component 2 Composition:\n\n" +
        '\n'.join(f"{col}: {contributions_dataframe[col].iloc[1]:.2f}%" for col in contributions_dataframe.columns),
        bbox=dict(fc="lightgreen", alpha=0.5, boxstyle="round"),
        transform=control_axes.transAxes,
        verticalalignment='top',
        size=7
        )
    return pca1_text, pca2_text


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


# -- CLASSIFICATION FUNCTIONS -------------------------------------------------

def _plot_classified_data(data_axes: Axes, data: np.ndarray, k: int, seed: int):
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
    data_axes.set_title("K-Means Clustering")

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


def _build_classification_cursor(
        plot,
        data: pd.DataFrame,
        kmeans: KMeans,
        colormap
        ):
    """Build a cursor for the scatter plot that shows detailed information
    about each point when hovered over.

    Args:
        plot: The scatter plot to attach the cursor to.
        data: The original DataFrame containing the trading data, used to
        display detailed information in the hover annotations.
        kmeans: The fitted KMeans model, used to display the cluster label in
        the hover annotations.
        colormap: The colormap used for plotting, used to set the background
        color of the hover annotations based on the cluster label.

    Returns:
        The created mplcursors.Cursor object.
    """
    cursor = mplcursors.cursor(plot, hover=mplcursors.HoverMode.Transient)

    @cursor.connect("add")
    def on_add(sel):
        index = sel.index

        local_data = data.iloc[[index]]
        numeric_columns = local_data.select_dtypes(include='number').columns
        local_data[numeric_columns] = local_data[numeric_columns].round(4)
        sel.annotation.set_text(
            f"Start Timestamp: {local_data.index[0]}\n" +
            '\n'.join(f"{COL_NAMES.get(col, col)}: {local_data[col].iloc[0]}" for col in data.columns) +
            f"\nCluster: {kmeans.labels_[index]}"  # type: ignore
            )
        sel.annotation.get_bbox_patch().set_alpha(0.95)
        sel.annotation.get_bbox_patch().set_facecolor(
            colormap(kmeans.labels_[index])  # type: ignore
            )

    return cursor


def _kmeans_gui(
        fig: Figure,
        data: np.ndarray,
        df: pd.DataFrame,
        control_axes: Axes,
        data_axes: Axes,
        cursor: mplcursors.Cursor
        ):
    """Create a GUI for adjusting the number of clusters (k) and random seed
    for k-means clustering.

    Args:
        fig: The figure to add the GUI to.
        data: The PCA-transformed data to plot.
        df: The original DataFrame containing the trading data, used for hover
        annotations.
        control_axes: The axes to add the GUI controls to.
        data_axes: The axes to update with the new clustering results when the
        controls are adjusted.
        cursor: The mplcursors.Cursor object to update with the new clustering
        results when the controls are adjusted.

    Returns:
        The TextBox widgets for k and random seed since matplotlib requires
        keeping references to them to prevent garbage collection.
        Also returns the updated cursor object after adjusting the clustering
        results.
    """
    # Render GUI components
    k_axes = control_axes.inset_axes((0.6, 0.95, 0.42, 0.04))
    k_label = widgets.TextBox(
        k_axes,
        label="Number of Clusters (k): ",
        initial="10"
        )
    seed_axes = control_axes.inset_axes((0.4, 0.9, 0.62, 0.04))
    seed_label = widgets.TextBox(
        seed_axes,
        label="Random Seed (Clustering): ",
        initial="0"
        )

    # Update the plot when the user submits new values for k or random seed
    def change_kmeans(label):
        nonlocal cursor

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

        kmeans, scatter, colormap = _plot_classified_data(data_axes, data, k, seed)
        # Rebuild the cursor, too
        cursor.remove()
        cursor = _build_classification_cursor(scatter, df, kmeans, colormap)
        fig.canvas.draw_idle()

    k_label.on_submit(change_kmeans)
    seed_label.on_submit(change_kmeans)

    return k_label, seed_label, cursor


def _classify_bots(
        data: pd.DataFrame,
        pca_features: np.ndarray,
        fig: Figure,
        axes: Axes,
        control_axes: Axes
        ):
    # Preprocess data and perform PCA
    # Perform k-means clustering and plot the classified data
    kmeans, scatter, colormap = _plot_classified_data(
            axes,
            pca_features,
            10,
            seed=0
            )

    # Create cursor for hover annotations
    cursor = _build_classification_cursor(scatter, data, kmeans, colormap)

    # Show the GUI for adjusting k and random seed
    *widgets, cursor = _kmeans_gui(fig, pca_features, data, control_axes, axes, cursor)

    return widgets, cursor


# -- OUTLIER DETECTION FUNCTIONS ----------------------------------------------

def _plot_isolation_data(
        data: np.ndarray,
        pca_features: np.ndarray,
        isolation_axes: Axes,
        tree_count: int,
        seed: int,
        enable_inliers: bool = True,
        enable_outliers: bool = True
        ):
    """Plot the data points in a 2D PCA space, colored by their isolation
    forest labels.

    Args:
        isolation_axes: The axes to plot the data on.
        data: The preprocessed data to plot.
        tree_count: The number of trees to use for the isolation forest.
        seed: The random seed to use for the isolation forest.

    Returns:
        The fitted IsolationForest model, the scatter plot object, and the
        fitted PCA model.
    """
    # Perform isolation forest outlier detection
    isolation = IsolationForest(
        n_estimators=tree_count,
        random_state=seed
        )
    labels = isolation.fit_predict(data)
    isolation_axes.clear()

    if not enable_inliers:
        pca_features = pca_features[labels != 1]
        labels = labels[labels != 1]
    if not enable_outliers:
        pca_features = pca_features[labels != -1]
        labels = labels[labels != -1]

    # Plot the data points
    colormap = plt.get_cmap("coolwarm_r", 2)
    isolation_scatter = isolation_axes.scatter(
            pca_features[:, 0],
            pca_features[:, 1],
            c=labels,
            cmap=colormap,
            edgecolor='k',
            alpha=0.6,
            s=10,
            picker=8
            )
    isolation_axes.set_xlabel("PCA Component 1")
    isolation_axes.set_ylabel("PCA Component 2")
    isolation_axes.set_title("Outlier Detection")

    return isolation, isolation_scatter,


def _build_isolation_cursor(
        isolation_scatter,
        data: pd.DataFrame,
        decision_scores: np.ndarray,
        ):
    """Build a cursor for the isolation forest scatter plot that shows detailed
    information about each point when hovered over, including the original data
    values and the isolation forest decision score.

    Args:
        isolation_scatter: The scatter plot to attach the cursor to.
        data: The original DataFrame containing the trading data, used to
        display detailed information in the hover annotations.
        decision_scores: The isolation forest decision scores for each data
        point, used to display the outlier score in the hover annotations and
        set the background color.

    Returns:
        The created mplcursors.Cursor object.
    """
    isolation_cursor = mplcursors.cursor(isolation_scatter, hover=mplcursors.HoverMode.Transient)

    @isolation_cursor.connect("add")
    def on_isolation_add(sel):
        index = sel.index

        local_data = data.iloc[[index]]
        numeric_columns = local_data.select_dtypes(include=[np.number]).columns
        local_data[numeric_columns] = local_data[numeric_columns].round(4)
        sel.annotation.set_text(
            f"Start Timestamp: {local_data.index[0]}\n" +
            '\n'.join(f"{COL_NAMES.get(col, col)}: {local_data[col].iloc[0]}" for col in data.columns) +
            f"\nOutlier Score: {decision_scores[index]:.4f}"  # type: ignore
            )
        sel.annotation.get_bbox_patch().set_alpha(0.95)
        sel.annotation.get_bbox_patch().set_facecolor(
            "darkred" if decision_scores[index] < 0 else "darkblue"
            )

    return isolation_cursor


def _outlier_detection_gui(
        fig: Figure,
        data: np.ndarray,
        df: pd.DataFrame,
        pca_features: np.ndarray,
        isolation_axes: Axes,
        control_axes: Axes,
        isolation_cursor: mplcursors.Cursor
        ):
    tree_axes = control_axes.inset_axes((0.6, 0.83, 0.42, 0.04))
    tree_label = widgets.TextBox(
        tree_axes,
        label="Number of Trees: ",
        initial="100"
        )
    seed_axes = control_axes.inset_axes((0.4, 0.78, 0.62, 0.04))
    seed_label = widgets.TextBox(
        seed_axes,
        label="Random Seed (Outlier): ",
        initial="0"
        )
    enable_axes = control_axes.inset_axes((0.4, 0.7, 0.62, 0.07))
    enable = widgets.CheckButtons(
        enable_axes,
        labels=["Show Inliers", "Show Outliers"],
        actives=[True, True]
        )

    def change_isolation(label):
        nonlocal isolation_cursor

        try:
            tree_count = int(tree_label.text)
            seed = int(seed_label.text)
            if tree_count <= 0:
                print("Warning: Number of trees must be positive, defaulting to 100")
                tree_count = 100
            if seed < 0:
                print("Warning: Random seed must be non-negative, defaulting to 0")
                seed = 0
        except ValueError:
            print("Warning: Invalid input for number of trees or random seed, defaulting to 100 trees and seed=0")
            tree_count = 100
            seed = 0

        isolation, scatter = _plot_isolation_data(
            data,
            pca_features,
            isolation_axes,
            tree_count,
            seed,
            enable_inliers=enable.get_status()[0],
            enable_outliers=enable.get_status()[1]
        )

        # Filter data and decision scores based on inliers/outliers checkboxes
        filtered_df = df.copy()
        filtered_decision_scores = isolation.decision_function(data)
        if not enable.get_status()[0]:
            filtered_df = filtered_df[filtered_decision_scores < 0]
            filtered_decision_scores = filtered_decision_scores[filtered_decision_scores < 0]
        if not enable.get_status()[1]:
            filtered_df = filtered_df[filtered_decision_scores >= 0]
            filtered_decision_scores = filtered_decision_scores[filtered_decision_scores >= 0]

        # Rebuild the cursor, too
        isolation_cursor.remove()
        isolation_cursor = _build_isolation_cursor(
            scatter,
            filtered_df,  # type: ignore
            filtered_decision_scores
        )
        fig.canvas.draw_idle()

    tree_label.on_submit(change_isolation)
    seed_label.on_submit(change_isolation)
    enable.on_clicked(change_isolation)

    return tree_label, seed_label, enable, isolation_cursor


def _detect_outliers(
        data: pd.DataFrame,
        scaled_features: np.ndarray,
        pca_features: np.ndarray,
        fig: Figure,
        axes: Axes,
        control_axes: Axes
        ):
    # Plot the isolation forest results
    isolation, scatter = _plot_isolation_data(
        scaled_features,
        pca_features,
        axes,
        tree_count=100,
        seed=0
        )

    # Create cursor for hover annotations
    isolation_cursor = _build_isolation_cursor(
        scatter,
        data,
        isolation.decision_function(scaled_features)
        )

    # Show the GUI for adjusting isolation forest parameters
    *widgets, isolation_cursor = _outlier_detection_gui(
        fig,
        scaled_features,
        data,
        pca_features,
        axes,
        control_axes,
        isolation_cursor
        )

    return widgets, isolation_cursor


# -- MAIN LOGIC ---------------------------------------------------------------

def classify_trades(files: list[str]):
    data = _collate_data(files)
    if data is None:
        print("Error: No valid data to classify")
        return

    features, scaled_features = _preprocess_data(data)
    pca = PCA(n_components=2, svd_solver="full")
    pca_features = pca.fit_transform(scaled_features)

    fig, (kmeans_axes, isolation_axes), control_axes = make_plot("Trading Bot Classification", 2)

    # Classify bots using k-means clustering
    *classification_widgets, classification_cursor = _classify_bots(
        data,
        pca_features,
        fig,
        kmeans_axes,
        control_axes
        )
    # Find outlier bots using isolation forest
    *isolation_widgets, isolation_cursor = _detect_outliers(
            data,
            scaled_features,
            pca_features,
            fig,
            isolation_axes,
            control_axes
            )

    # Show the PCA component contributions in the control panel
    _ = _pca_contributions(pca, features, control_axes)
    # Actually show the plot
    plt.show()
