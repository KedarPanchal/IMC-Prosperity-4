"""Classifies trading bots based on their behavior and characteristics.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplcursors

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# -- PRIVATE HELPERS ----------------------------------------------------------

def _pca(N: np.ndarray, d: int) -> np.ndarray:
    """Perform Principal Component Analysis (PCA) on a 4D dataset to produce
    its d-dimensional projection.

    Args:
        n: A 4D numpy array representing the dataset to be reduced.
        d: The target dimensionality for the PCA projection (e.g., 2 for 2D).
        Assumed to be less than or equal to the original dimensionality (4).

    Returns:
        A k x 3 numpy array containing the projection of the original data onto
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
    # Only include dataframes that contain the "buyer" column (trade data)
    dfs = list(
            filter(
                lambda d: "buyer" in d.columns,
                (pd.read_csv(file, sep=';') for file in files)
                )
            )
    if len(dfs) < len(files):
        print(f"Warning: {len(files) - len(dfs)} files were invalid")
    return pd.concat(dfs, ignore_index=True)


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
    # Drop columns for timestep, buyer, seller, and currency
    features = data.drop(
            columns=["timestamp", "buyer", "seller", "currency"],
            errors="ignore"
            )
    # Perform 1-hot encoding for purchased items
    features = pd.get_dummies(features, columns=["symbol"], drop_first=True)
    # Normalize the features
    scaler = StandardScaler()
    features_norm = scaler.fit_transform(features.to_numpy())
    # Perform k-means clustering
    kmeans = KMeans(n_clusters=clusters, random_state=0)
    kmeans.fit(features_norm)

    # Plot the clusters in 3D, since their dimension is 3D anyway
    fig = plt.figure(figsize=(16, 8))
    axes = fig.add_subplot(1, 1, 1, projection="3d")
    colormap = plt.get_cmap("viridis", clusters)
    scatter = axes.scatter(
            features_norm[:, 0],
            features_norm[:, 1],
            features_norm[:, 2],
            c=kmeans.labels_,
            cmap=colormap,
            edgecolor='k',
            alpha=0.6,
            s=10,
            picker=8
            )
    axes.set_xlabel("Symbol (One-Hot Encoded)")
    axes.set_ylabel("Price (Normalized)")
    axes.set_zlabel("Quantity (Normalized)")
    axes.set_title("K-Means Clustering of Trading Bots")

    # Extract relevant features for hover annotations
    hover_data = data[["timestamp", "symbol", "price", "quantity"]].to_numpy()

    # Create cursor for hover annotations
    cursor = mplcursors.cursor(scatter, hover=mplcursors.HoverMode.Transient)

    @cursor.connect("add")
    def on_add(sel):
        index = sel.index
        timestamp, symbol, price, quantity = hover_data[index]
        sel.annotation.set_text(f"Timestamp: {timestamp}\nSymbol: {symbol}\nPrice: {price}\nQuantity: {quantity}\nCluster: {kmeans.labels_[index]}")  # type: ignore
        sel.annotation.get_bbox_patch().set_alpha(0.9)
        sel.annotation.get_bbox_patch().set_facecolor(
            colormap(kmeans.labels_[index])  # type: ignore
            )

    # Actually plot the clusters
    fig.colorbar(scatter, ax=axes, label="Cluster Label")
    plt.show()
