"""Classifies trading bots based on their behavior and characteristics.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from scipy.spatial import Voronoi, voronoi_plot_2d


# -- PRIVATE HELPERS ----------------------------------------------------------

def _gram_schmidt2D(
        v1: np.ndarray,
        v2: np.ndarray
        ) -> tuple[np.ndarray, np.ndarray]:
    """Apply the Gram-Schmidt process to orthogonalize two 4D vectors for 2D
    projection.

    The first vector is held constant, and the second vector is modified to be
    orthogonal to the first.

    Args:
        v1: The first 4D vector to be orthogonalized.
        v2: The second 4D vector to be orthogonalized with respect to the
        first.

    Returns:
        A tuple of the original first vector and the orthogonalized second
        vector.
    """
    # Normalize vector1
    v1_norm = v1 / np.linalg.norm(v1)

    # Project vector2 onto vector1
    s = np.dot(v1_norm, v2) / np.linalg.norm(v2) * v1_norm
    # Compute the orthogonal component of vector1 with respect to vector2
    v2_orthogonal = v2 - s
    v2_orthogonal_norm = v2_orthogonal / np.linalg.norm(v2_orthogonal)
    return v1_norm, v2_orthogonal_norm


def collate_data(files: list[str]) -> pd.DataFrame:
    """Collate data from multiple files into a single dataset for
    classification.

    Combines data from the provided files, ensuring that only valid dataframes
    for trading bot classification are included.

    Args:
        files: List of file paths to collate data from.

    Returns:
        A single DataFrame containing the collated data from all valid files.
    """
    # Placeholder for data collation logic
    dfs = filter(lambda d: "buyer" in d.columns, (pd.read_csv(file, sep=';') for file in files))
    dfs = [d for d in dfs if "buyer" in d.columns]
    if len(list(dfs)) < len(files):
        print(f"Warning: {len(files) - len(list(dfs))} files were invalid")
    return pd.concat(dfs, ignore_index=True)


def classify_bots(data: pd.DataFrame, clusters: int) -> None:
    """Classify trading bots based on their behavior and characteristics.

    Uses k-means clustering to group bots into distinct categories based on
    their trading patterns and features.

    Args:
        data: DataFrame containing the trading data for classification.
        clusters: The number of clusters to use for classification.

    Returns:
        TBD
    """
    # Drop columns for timestep, buyer, seller, and currency
    features = data.drop(columns=["timestamp", "buyer", "seller", "currency"])
    # Perform 1-hot encoding for purchased items
    features = pd.get_dummies(features, columns=["symbol"])
    # Normalize the features
    scaler = StandardScaler()
    features_norm = scaler.fit_transform(features.to_numpy())
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=clusters, random_state=0)
    kmeans.fit(features_norm)

    # The fitted data is 4D
    # To visualize, define a projection matrix to project the data into 2D
    p1, p2 = _gram_schmidt2D(
        np.array([1, 1, 1, 0]),
        np.array([0, 1, 1, 1])
        )
    projection_matrix = np.array([p1, p2]).T

    # Project the cluster centers into 2D
    centers_2d = kmeans.cluster_centers_ @ projection_matrix
    vornoi_cells = Voronoi(centers_2d)
    fig = voronoi_plot_2d(vornoi_cells)
    plt.show()
