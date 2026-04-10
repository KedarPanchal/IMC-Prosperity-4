#!/bin/bash

# Ensure all backtesters are installed and up to date
uv sync

# The first argument is which backtester to use
backtester="$1"

if [[ "$backtester" == "zeeshan" ]]; then
    uv run prosperity4btx "$@"
elif [[ "$backtester" == "nabayansaha" ]]; then
    uv run prosperity4btest "$@"
elif [[ "$backtester" == "jmerle" ]]; then
    uv run prosperity3bt "$@"
else
    echo "Unknown backtester: $backtester"
fi
