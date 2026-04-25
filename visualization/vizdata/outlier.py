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

def _plot_data(data_axes: Axes, data: np.ndarray, outliers: np.ndarray):
    pass


def _outliers_gui(
        fig: Figure,
        data_axes: Axes,
        data: np.ndarray,
        outliers: np.ndarray
        ):
    pass


# -- MAIN LOGIC ---------------------------------------------------------------

def detect_outliers(data: pd.DataFrame):
    # Preprocess the data
    dropped, features, scaled = preprocess_data(data)
