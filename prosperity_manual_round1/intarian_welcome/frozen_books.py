"""
Stale order-book snapshots from the Intarian Welcome manual challenge.

Each book is a pair of dicts: price -> aggregate resting volume at that level.
"""

from __future__ import annotations

from typing import Final

# Dryland Flax — resting liquidity only (no player order).
DRYLAND_FLAX_BIDS: Final[dict[int, int]] = {
    30: 30_000,
    29: 5_000,
    28: 12_000,
    27: 28_000,
}
DRYLAND_FLAX_ASKS: Final[dict[int, int]] = {
    28: 40_000,
    31: 20_000,
    32: 20_000,
    33: 30_000,
}

# Ember Mushroom — resting liquidity only.
EMBER_MUSHROOM_BIDS: Final[dict[int, int]] = {
    20: 43_000,
    19: 17_000,
    18: 6_000,
    17: 5_000,
    16: 10_000,
}
EMBER_MUSHROOM_ASKS: Final[dict[int, int]] = {
    12: 20_000,
    13: 25_000,
    14: 35_000,
    15: 6_000,
    16: 5_000,
}

DRYLAND_FLAX_BOOK: Final[tuple[dict[int, int], dict[int, int]]] = (
    DRYLAND_FLAX_BIDS,
    DRYLAND_FLAX_ASKS,
)
EMBER_MUSHROOM_BOOK: Final[tuple[dict[int, int], dict[int, int]]] = (
    EMBER_MUSHROOM_BIDS,
    EMBER_MUSHROOM_ASKS,
)
