# pyright: reportUnusedFunction=false

import argparse
import os

from vizdata.analysis import analyze_data
from vizdata.botclassifier import collate_data, classify_bots


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
            choices=["analysis", "classification"],
            default="analysis",
            help="Mode of operation: 'analysis' for visualization, 'classification' for bot classification"
            )
    args = parser.parse_args()

    # Parsing files must be passed
    if not args.files:
        parser.error("No files to parse")

    files = []
    for file in args.files:
        if os.path.isfile(file):
            files.append(file)
        else:
            parser.error(f"Unknown file: {file}")

    if args.mode == "analysis":
        analyze_data(files)
    elif args.mode == "classification":
        # Placeholder for classification logic
        data = collate_data(files)
        if data is None:
            parser.error("No valid data for classification")
        classify_bots(data)


if __name__ == "__main__":
    main()
