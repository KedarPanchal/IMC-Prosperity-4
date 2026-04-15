# pyright: reportUnusedFunction=false

import argparse
import os

from vizdata.analysis import analyze_data
from vizdata.denoise import DENOISING_STRATEGIES


# -- CLI ----------------------------------------------------------------------

def main():
    """Parse CLI paths and run ``analyze_data`` on each existing file."""

    parser = argparse.ArgumentParser(
            description="Visualize trade and price data from CSV files."
            )
    parser.add_argument(
            "--files",
            "-f",
            dest="files",
            nargs="*",
            help="Paths to CSV files for analysis"
            )

    subparser = parser.add_subparsers(dest="command", required=False)
    denoise_parser = subparser.add_parser(
            "denoise",
            help="Denoise the data before plotting",
            )
    denoise_parser.add_argument(
            "--strategy",
            "-s",
            dest="strategy",
            choices=list(DENOISING_STRATEGIES.keys()),
            default="identity",
            help="Which denoising algorithm to utilize when denoising the data"
            )
    denoise_parser.add_argument(
            "--passes",
            "-p",
            dest="passes",
            type=int,
            default=2,
            help="The number of passes to perform the Fourier transform for"
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

    for file in files:
        analyze_data(
                file,
                "haar" if args.command == "denoise" else "identity",
                args.passes if args.command == "denoise" else 0
                )


if __name__ == "__main__":
    main()
