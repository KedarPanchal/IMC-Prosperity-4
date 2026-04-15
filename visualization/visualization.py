# pyright: reportUnusedFunction=false

import argparse
import os

from vizdata.analysis import analyze_data
from vizdata.denoise import DENOISING_STRATEGIES
from vizdata.botclassifier import collate_data, classify_bots


# -- CLI ----------------------------------------------------------------------

def main():
    """Parse CLI paths and run ``analyze_data`` on each existing file."""

    # Create base parser containing shared logic across commands
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument(
            "--files",
            "-f",
            dest="files",
            nargs="*",
            help="Paths to CSV files for analysis"
            )

    # Create main parser and subparsers for different analysis commands
    parser = argparse.ArgumentParser(
        description="Visualize trade and price data from CSV files.",
        )
    subparser = parser.add_subparsers(dest="command", required=True)

    analysis_parser = subparser.add_parser(
            "analysis",
            parents=[base_parser],
            help="Perform visualization with optional data denoising"
            )
    analysis_parser.add_argument(
        "--strategy",
        "-s",
        dest="strategy",
        choices=list(DENOISING_STRATEGIES.keys()),
        default="identity",
        help="Which denoising algorithm to utilize when denoising the data"
        )
    analysis_parser.add_argument(
            "--passes",
            "-p",
            dest="passes",
            type=int,
            default=2,
            help="The number of passes to perform the Fourier transform for"
            )

    classification_parser = subparser.add_parser(
            "classification",
            parents=[base_parser],
            help="Classify bots based on trading data"
            )
    classification_parser.add_argument(
            "--clusters",
            "-k",
            dest="clusters",
            type=int,
            default=10,
            help="The number of clusters to use for bot classification"
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

    if args.command == "analysis":
        for file in files:
            analyze_data(
                file,
                args.strategy,
                args.passes
            )
    elif args.command == "classification":
        # Placeholder for classification logic
        data = collate_data(files)
        classify_bots(data, args.clusters)


if __name__ == "__main__":
    main()
