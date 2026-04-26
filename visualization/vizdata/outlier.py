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
from sklearn.decomposition import PCA

from .mlutils import make_plot, pca_contributions, preprocess_data, COL_NAMES


# -- PRIVATE HELPERS ----------------------------------------------------------

def _plot_isolation_data(
        isolation_axes: Axes,
        data: np.ndarray,
        tree_count: int,
        seed: int
        ):
    """Plot the data points in a 2D PCA space, colored by their isolation 
    forest labels.

    Args:
        isolation_axes: The axes to plot the data on.
        data: The preprocessed data to plot.
        tree_count: The number of trees to use for the isolation forest.
        seed: The random seed to use for the isolation forest.

    Returns:
        The fitted IsolationForest model, the scatter plot object, the colormap
        used for plotting, and the fitted PCA model.
    """
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

    return isolation, isolation_scatter, colormap, pca


def _plot_decision_data(
        isolation: IsolationForest,
        decision_axes: Axes,
        data: np.ndarray
        ):
    """Plot the isolation forest decision scores for each data point, sorted
    by score.

    Args:
        isolation: The fitted IsolationForest model.
        decision_axes: The axes to plot the decision scores on.
        data: The preprocessed data to compute the decision scores for.

    Returns:
        The decision scores for each data point and the line plot object.
    """
    decision_scores = isolation.decision_function(data)
    decision_axes.clear()
    decision_graph = decision_axes.plot(
        range(len(decision_scores)),
        sorted(decision_scores),
        color="black",
        alpha=0.6,
        picker=8
        )
    decision_axes.set_xlabel("Data Point Index (sorted by score)")
    decision_axes.set_ylabel("Isolation Forest Decision Score")

    return decision_scores, decision_graph


def _outliers_gui(
        fig: Figure,
        data: np.ndarray,
        df: pd.DataFrame,
        isolation_axes: Axes,
        decision_axes: Axes,
        control_axes: Axes,
        isolation_cursor: mplcursors.Cursor,
        decision_cursor: mplcursors.Cursor
        ):
    """Create a GUI for adjusting the number of trees and random seed for the
    isolation forest, and update the plots accordingly.

    Args:
        fig: The figure to add the GUI to.
        data: The preprocessed data to plot.
        df: The original DataFrame containing the data (for annotations).
        isolation_axes: The axes to update with the new isolation forest
        results when the controls are adjusted.
        decision_axes: The axes to update with the new decision scores when the
        controls are adjusted.
        control_axes: The axes to add the GUI controls to.
        isolation_cursor: The mplcursors.Cursor object for the isolation plot,
        to update with the new isolation forest results when the controls are
        adjusted.
        decision_cursor: The mplcursors.Cursor object for the decision score
        plot, to update with the new decision scores when the controls are
        adjusted.

    Returns:
        The TextBox widgets for the number of trees and random seed, and the
        updated mplcursors.Cursor objects for the isolation and decision score
        plots.
    """
    tree_axes = control_axes.inset_axes((0.6, 0.95, 0.42, 0.04))
    tree_label = widgets.TextBox(
        tree_axes,
        label="Number of Trees: ",
        initial="100"
        )
    seed_axes = control_axes.inset_axes((0.4, 0.90, 0.62, 0.04))
    seed_label = widgets.TextBox(
        seed_axes,
        label="Random Seed: ",
        initial="0"
        )

    def change_isolation(label):
        nonlocal isolation_cursor, decision_cursor

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
            print("Warning: Invalid input for number of trees or random seed, defaulting to 100 trees and seed 0")
            tree_count = 100
            seed = 0

        isolation, isolation_scatter, isolation_colormap, *_ = _plot_isolation_data(
            isolation_axes,
            data,
            tree_count=tree_count,
            seed=seed
            )
        decision_scores, _ = _plot_decision_data(
            isolation,
            decision_axes,
            data
            )
        # Rebuild the cursors, too
        isolation_cursor.remove()
        decision_cursor.remove()
        isolation_cursor = _build_isolation_cursor(
            isolation_scatter,
            df,
            data,
            isolation,
            decision_scores,
            isolation_colormap
            )
        fig.canvas.draw_idle()

    tree_label.on_submit(change_isolation)
    seed_label.on_submit(change_isolation)

    return tree_label, seed_label, isolation_cursor, decision_cursor


def _build_isolation_cursor(
        isolation_scatter,
        data: pd.DataFrame,
        scaled: np.ndarray,
        isolation: IsolationForest,
        decision_scores: np.ndarray,
        isolation_colormap
        ):
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
            isolation_colormap(isolation.predict(scaled)[index])  # type: ignore
            )

    return isolation_cursor


def _build_decision_cursor(decision_graph, decision_scores: np.ndarray):
    sorted_decision_scores = sorted(decision_scores)
    decision_cursor = mplcursors.cursor(decision_graph, hover=mplcursors.HoverMode.Transient)

    @decision_cursor.connect("add")
    def on_decision_add(sel):
        index = int(sel.index)

        sel.annotation.set_text(
            f"Outlier Score: {sorted_decision_scores[index]:.4f}"  # type: ignore
            )
        sel.annotation.get_bbox_patch().set_alpha(0.95)
        sel.annotation.get_bbox_patch().set_facecolor("red" if sorted_decision_scores[index] < 0 else "green")  # type: ignore

    return decision_cursor


# -- MAIN LOGIC ---------------------------------------------------------------

def detect_outliers(data: pd.DataFrame):
    # Preprocess the data
    features, scaled = preprocess_data(data)
    fig, (isolation_axes, split_axes), control_axes = make_plot("Outlier Detection", 2)
    isolation, isolation_scatter, isolation_colormap, pca = _plot_isolation_data(
        isolation_axes,
        scaled,
        tree_count=100,
        seed=0
        )
    decision_scores, decision_graph = _plot_decision_data(
        isolation,
        split_axes,
        scaled
        )

    # Create cursor for hover annotations
    isolation_cursor = _build_isolation_cursor(
        isolation_scatter,
        data,
        scaled,
        isolation,
        decision_scores,
        isolation_colormap
        )
    decision_cursor = _build_decision_cursor(decision_graph, decision_scores)
    # Show the GUI for adjusting isolation forest parameters
    # Also show the PCA component contributions
    *_, isolation_cursor, decision_cursor = _outliers_gui(
        fig,
        scaled,
        data,
        isolation_axes,
        split_axes,
        control_axes,
        isolation_cursor,
        decision_cursor
        )
    pca_contributions(pca, features, control_axes)
    # Actually plot the outliers
    plt.show()
