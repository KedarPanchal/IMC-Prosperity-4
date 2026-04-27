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
