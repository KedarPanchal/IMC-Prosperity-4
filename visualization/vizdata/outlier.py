"""Identifies outliers in bot trading behavior
"""

import pandas as pd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.widgets as widgets
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import mplcursors

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

from .mlutils import make_plot, pca_contributions, preprocess_data


# -- PRIVATE HELPERS ----------------------------------------------------------

def _plot_data(
        isolation_axes: Axes,
        data: np.ndarray,
        tree_count: int,
        seed: int
        ):
    # Perform isolation forest outlier detection
    isolation = IsolationForest(
        n_estimators=tree_count,
        random_state=seed
        )
    labels = isolation.fit_predict(data)
    isolation_axes.clear()

    # Transform data to 2D space for visualization
    pca = PCA(n_components=2, svd_solver="full")
    pca_features = pca.fit_transform(data)

    # Plot the data points
    colormap = plt.get_cmap("coolwarm", 2)
    scatter = isolation_axes.scatter(
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
    return isolation, scatter, colormap, pca


def _outliers_gui(
        fig: Figure,
        data_axes: Axes,
        data: np.ndarray,
        ):
    pass


# -- MAIN LOGIC ---------------------------------------------------------------

def detect_outliers(data: pd.DataFrame):
    # Preprocess the data
    dropped, features, scaled = preprocess_data(data)
    fig, (isolation_axes, split_axes), control_axes = make_plot("Outlier Detection", 2)
    isolation, scatter, colormap, pca = _plot_data(
        isolation_axes,
        scaled,
        tree_count=100,
        seed=0
        )

    # Create cursor for hover annotations

    # Show the PCA component contributions
    pca_contributions(pca, features, control_axes)
    # Actually plot the outliers
    plt.show()
