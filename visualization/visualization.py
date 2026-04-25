# pyright: reportUnusedFunction=false

import argparse
import os

from vizdata.analysis import analyze_data
from vizdata.mlutils import collate_data
from vizdata.botclassifier import classify_bots
from vizdata.outlier import detect_outliers


# -- CLI ----------------------------------------------------------------------

def main():
    """Parse CLI paths and run ``analyze_data`` on each existing file."""

    # Create base parser containing shared logic across commands
    parser = argparse.ArgumentParser(
            add_help=True,
            description="Visualize and analyze IMC Prosperity 4 data from CSV files."
            )
    parser.add_argument(
            "--files",
            "-f",
            dest="files",
            nargs="*",
            help="Paths to CSV files for analysis"
            )
    parser.add_argument(
            "--mode",
            "-m",
            dest="mode",
            choices=["analysis", "classification", "outlier"],
            default="analysis",
            help="Mode of operation: 'analysis' (default) for visualization, "
                    "'classification' for bot detection"
                    "'outlier' for outlier detection"
            )
    args = parser.parse_args()

    # Parsing files must be passed
    if not args.files:
        parser.error("No files to parse")

    files = []
    for file in args.files:
        if os.path.isfile(file) and file.endswith(".csv"):
            files.append(file)
        else:
            if os.path.isfile(file):
                print(f"File is not a CSV, skipping: {file}")
            else:
                print(f"Unknown file, skipping: {file}")

    if args.mode == "analysis":
        analyze_data(files)
    elif args.mode == "classification":
        # Placeholder for classification logic
        data = collate_data(files)
        if data is None:
            parser.error("No valid data for classification")
        classify_bots(data)
    elif args.mode == "outlier":
        data = collate_data(files)
        if data is None:
            parser.error("No valid data for outlier detection")
        detect_outliers(data)
    else:
        parser.error(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
