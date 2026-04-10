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
else
    echo "Unknown backtester: $backtester"
    echo "Available options are: zeeshan, nabayansaha, jmerle"
fi

# Return to the original directory
cd "$OLDPWD"
