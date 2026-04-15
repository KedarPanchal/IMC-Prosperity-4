"""Classifies trading bots based on their behavior and characteristics.
"""

import sklearn as sk
import pandas as pd


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
