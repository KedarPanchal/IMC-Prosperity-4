#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Ensure all backtesters are installed and up to date
uv sync

# The first argument is which backtester to use
backtester="$1"

# Forward the rest of the arguments to the selected backtester
if [[ "$backtester" == "zeeshan" ]]; then
    uv run prosperity4btx "$@"
elif [[ "$backtester" == "nabayansaha" ]]; then
    uv run prosperity4btest "$@"
elif [[ "$backtester" == "jmerle" ]]; then
    uv run prosperity3bt "$@"
elif [[ "$backtester" == "--help" || "$backtester" == "-h" ]]; then
    echo "Usage: $0 [backtester] [options]"
    echo "Available backtesters:"
    echo "  zeeshan       - Run Zeeshan's backtester"
    echo "  nabayansaha   - Run Nabayansaha's backtester"
    echo "  jmerle        - Run Jmerle's backtester"
    uv run prosperity3bt --help
else
    echo "Unknown backtester: $backtester"
    echo "Available options are: zeeshan, nabayansaha, jmerle"
    echo "Run '$0 --help' for more information."
fi

# Return to the original directory
cd "$OLDPWD"
