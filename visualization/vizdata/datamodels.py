"""Data models for trade and price data, and helper functions to load them
"""

import pandas as pd
from typing import Any


# -- PRIVATE HELPERS ----------------------------------------------------------

def _castable(value, to_type):
    """Return whether ``value`` can be converted with ``to_type`` without
    error.

    Args:
        value: Value to convert.
        to_type: Callable used like ``to_type(value)``
        (e.g. ``float``, ``int``).

    Returns:
        True if conversion succeeds; False if ``ValueError`` or ``TypeError``
        is raised.
    """
    try:
        to_type(value)
        return True
    except ValueError:
        return False
    except TypeError:
        return False


def _avg(values: list):
    """Compute the mean of values that are finite and castable to float.

    Entries that are NaN or not castable to ``float`` are omitted.

    Args:
        values: Iterable of values to average.

    Returns:
        Arithmetic mean of the kept values, or ``0`` if none qualify.
    """
    actual = list(
            filter(
                lambda v: pd.notna(v) and _castable(v, float),
                values,
                )
            )
    return sum(map(float, actual)) / len(actual) if actual else 0


# -- OBJECT LOADER ------------------------------------------------------------

def load_objects(
        obj: type,
        data: pd.DataFrame,
        dict_: dict[Any, list],
        key: str
        ):
    """Build ``obj`` instances from dataframe rows and group them by a column
    key.

    Each row is passed to ``obj`` as keyword arguments. After loading, each
    list
    is sorted by a ``timestamp`` attribute.

    Args:
        obj: Class to instantiate for each row (must accept row fields as
        kwargs).
        data: Source table.
        dict_: Mapping from ``row[key]`` to lists of instances; updated in
        place. Must be a defaultdict or default-initialize missing keys to
        empty lists.
        key: Column name whose values are the grouping keys.

    Returns:
        None.
    """
    for _, row in data.iterrows():
        dict_[row[key]].append(obj(**row.to_dict()))  # type: ignore

    for obj_list in dict_.values():
        obj_list.sort()


# -- DATA MODELS --------------------------------------------------------------

class TradeData:
    """One trade row: timestamp, symbol, quantity, and price."""

    def __init__(
            self,
            **kwargs
            ):
        """Initialize from keyword arguments for the expected CSV columns.

        Args:
            **kwargs: Must include ``timestamp``, ``symbol``, ``quantity``,
            and ``price``.
        """
        self.timestamp = int(kwargs["timestamp"])
        self.symbol = str(kwargs["symbol"])
        self.quantity = int(kwargs["quantity"])
        self.price = float(kwargs["price"])

    def __lt__(self, other):
        """Return whether this trade is earlier than ``other`` by timestamp."""
        return self.timestamp < other.timestamp


class PriceData:
    """One order-book snapshot with averaged bid/ask prices and volumes."""

    def __init__(
            self,
            **kwargs
            ):
        """Initialize from keyword arguments; top three bid/ask levels are
        averaged.

        Args:
            **kwargs: Must include ``timestamp``, ``product``, ``bid_price_*``,
                ``ask_price_*``, ``bid_volume_*``, and ``ask_volume_*`` fields
                used below.
        """
        self.timestamp = int(kwargs["timestamp"])
        self.product = str(kwargs["product"])
        self.bid_price = _avg(
                [
                    kwargs["bid_price_1"],
                    kwargs["bid_price_2"],
                    kwargs["bid_price_3"],
                    ],
                )
        self.ask_price = _avg(
                [
                    kwargs["ask_price_1"],
                    kwargs["ask_price_2"],
                    kwargs["ask_price_3"],
                    ],
                )
        self.bid_volume = _avg(
                [
                    kwargs["bid_volume_1"],
                    kwargs["bid_volume_2"],
                    kwargs["bid_volume_3"],
                    ],
                )
        self.ask_volume = _avg(
                [
                    kwargs["ask_volume_1"],
                    kwargs["ask_volume_2"],
                    kwargs["ask_volume_3"],
                    ],
                )
        self.mid_price = kwargs["mid_price"]

    def __lt__(self, other):
        """Return whether this update is earlier than ``other`` by
        timestamp.
        """
        return self.timestamp < other.timestamp
