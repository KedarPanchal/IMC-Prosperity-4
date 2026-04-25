"""Classifies trading bots based on their behavior and characteristics.
"""

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.widgets as widgets
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import mplcursors
from scipy.spatial import Voronoi, voronoi_plot_2d

from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

from .mlutils import make_plot, pca_contributions, preprocess_data, COL_NAMES


# -- PRIVATE HELPERS ----------------------------------------------------------

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


def _kmeans_gui(
        fig: Figure,
        data: np.ndarray,
        control_axes: Axes,
        data_axes: Axes
        ):
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


# -- MAIN LOGIC ---------------------------------------------------------------

def classify_bots(data: pd.DataFrame) -> None:
    """Classify trading bots based on their behavior and characteristics.

    Uses k-means clustering to group bots into distinct categories based on
    their trading patterns and features.

    Args:
        data: DataFrame containing the trading data for classification.

    Returns:
        None.
    """
    # Preprocess data and perform PCA
    dropped, features, scaled = preprocess_data(data)
    pca = PCA(n_components=2, svd_solver="full")
    pca_features = pca.fit_transform(scaled)

    # Perform k means clustering and plot the results
    fig, axes, control_axes = make_plot("Trading Bot Classification", 1)
    # Since we only have 1 plot, just index into the first element
    axes = axes[0]  # type: ignore
    kmeans, scatter, colormap = _plot_data(axes, pca_features, 10, seed=0)

    # Create cursor for hover annotations
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
    pca_contributions(pca, features, control_axes)
    # Actually plot the clusters
    plt.show()
