"""
Grid search over (side, price, quantity) and reporting helpers.

Casual: Blast a ton of strategies and rank them.
Formal: Deterministic EV surface; optional refinement near argmax.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np

from intarian_welcome.clearing_simulator import (
    ClearingOutcome,
    ClearingSimulator,
    OrderSide,
    ProductParams,
)


@dataclass(frozen=True)
class CandidateRow:
    """One evaluated strategy row for export."""

    product: str
    side: str
    limit_price: int
    quantity: int
    clearing_price: float | None
    max_volume: int
    user_filled_qty: int
    profit: float
    per_unit_marginal: float


def _logspace_ints(lo: int, hi: int, n: int) -> list[int]:
    """Roughly log-spaced integers in [lo, hi] inclusive, unique sorted."""

    if hi < lo:
        return []
    if n <= 1:
        return [hi]
    xs = set()
    for i in range(n):
        if lo <= 0:
            t = lo + int(round((hi - lo) * (math.exp(i / max(n - 1, 1)) - 1) / (math.e - 1)))
        else:
            t = int(round(lo * (hi / lo) ** (i / max(n - 1, 1))))
        t = max(lo, min(hi, t))
        xs.add(t)
    xs.add(lo)
    xs.add(hi)
    return sorted(xs)


def build_quantity_grid(
    cap: int,
    linear_step: int,
    log_samples: int,
    dense_through: int | None = None,
) -> list[int]:
    """
    Multi-resolution quantity grid: optional **every integer** 1..dense_through
    (knife-edge quantities), plus linear coarse steps + log oversampling.

    Casual: Cover big range without a million points; dense_through catches 4999/19999-style cliffs.
    """

    if cap <= 0:
        return [1]
    qs: set[int] = {1}
    dense = min(cap, dense_through if dense_through is not None else 0)
    if dense > 0:
        qs.update(range(1, dense + 1))
    for q in range(linear_step, cap + 1, linear_step):
        qs.add(q)
    qs.add(cap)
    qs.update(_logspace_ints(1, cap, log_samples))
    return sorted(q for q in qs if 1 <= q <= cap)


def default_price_range(bids: dict[int, int], asks: dict[int, int]) -> tuple[int, int]:
    """Inclusive min/max over resting prices."""

    keys = set(bids) | set(asks)
    return min(keys), max(keys)


def iter_candidates(
    price_lo: int,
    price_hi: int,
    quantities: Sequence[int],
) -> Iterator[tuple[OrderSide, int, int]]:
    """Full factorial over both sides, prices, quantities."""

    for side in (OrderSide.BID, OrderSide.ASK):
        for price in range(price_lo, price_hi + 1):
            for qty in quantities:
                yield side, price, int(qty)


def evaluate_grid(
    sim: ClearingSimulator,
    params: ProductParams,
    price_lo: int,
    price_hi: int,
    quantities: Sequence[int],
) -> list[CandidateRow]:
    """Evaluate every candidate; returns rows (can be large)."""

    rows: list[CandidateRow] = []
    for side, price, qty in iter_candidates(price_lo, price_hi, quantities):
        out: ClearingOutcome = sim.simulate(side, price, qty)
        rows.append(
            CandidateRow(
                product=params.name,
                side=side.value,
                limit_price=price,
                quantity=qty,
                clearing_price=out.clearing_price,
                max_volume=out.max_volume,
                user_filled_qty=out.user_filled_qty,
                profit=out.profit,
                per_unit_marginal=out.per_unit_marginal,
            )
        )
    return rows


def rows_to_numpy_for_heatmap(
    rows: Sequence[CandidateRow],
    side: OrderSide,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build dense matrices for one side: profit[price_idx, qty_idx].

    Uses only rows matching `side`. Assumes factorial grid so we can reshape.
    """

    sub = [r for r in rows if r.side == side.value]
    if not sub:
        return np.array([]), np.array([]), np.array([])
    prices = sorted({r.limit_price for r in sub})
    qtys = sorted({r.quantity for r in sub})
    p_idx = {p: i for i, p in enumerate(prices)}
    q_idx = {q: j for j, q in enumerate(qtys)}
    grid = np.full((len(prices), len(qtys)), np.nan, dtype=float)
    for r in sub:
        grid[p_idx[r.limit_price], q_idx[r.quantity]] = r.profit
    return np.array(prices), np.array(qtys), grid


def top_k(rows: Sequence[CandidateRow], k: int) -> list[CandidateRow]:
    """Descending by profit."""

    return sorted(rows, key=lambda r: r.profit, reverse=True)[:k]


def compare_best_long_short(rows: Sequence[CandidateRow]) -> dict[str, Any]:
    """
    Compare best bid (long) vs best ask (short) outcomes on the same grid.

    Casual: See which side wins.
    Also reports best short **with positive fill** when possible (otherwise naked-max can be 0).
    """

    bids = [r for r in rows if r.side == OrderSide.BID.value]
    asks = [r for r in rows if r.side == OrderSide.ASK.value]
    best_bid = max(bids, key=lambda r: r.profit) if bids else None
    best_ask = max(asks, key=lambda r: r.profit) if asks else None
    asks_fill = [r for r in asks if r.user_filled_qty > 0]
    best_ask_filled = max(asks_fill, key=lambda r: r.profit) if asks_fill else None
    return {
        "best_long_row": best_bid,
        "best_short_row": best_ask,
        "best_short_row_positive_fill": best_ask_filled,
        "long_beats_short_profit": (best_bid.profit if best_bid else float("-inf"))
        >= (best_ask.profit if best_ask else float("-inf")),
    }


def knife_edge_near_best(
    sim: ClearingSimulator,
    row: CandidateRow,
    delta_qty: int = 1,
) -> dict[str, Any]:
    """
    Check whether P* jumps when nudging quantity by ±delta at same side/price.

    Casual: Spot tie-break cliffs next to a good-looking cell.
    """

    side = OrderSide(row.side)
    base = sim.simulate(side, row.limit_price, row.quantity)
    up = sim.simulate(side, row.limit_price, max(1, row.quantity + delta_qty))
    down = (
        sim.simulate(side, row.limit_price, max(1, row.quantity - delta_qty))
        if row.quantity > 1
        else None
    )
    return {
        "base_clearing": base.clearing_price,
        "up_clearing": up.clearing_price,
        "down_clearing": down.clearing_price if down else None,
        "p_star_jumps_up": base.clearing_price != up.clearing_price,
        "p_star_jumps_down": down is not None and base.clearing_price != down.clearing_price,
    }


def save_csv(rows: Sequence[CandidateRow], path: Path) -> None:
    """Write CSV with headers."""

    path.parent.mkdir(parents=True, exist_ok=True)
    import csv

    fieldnames = [
        "product",
        "side",
        "limit_price",
        "quantity",
        "clearing_price",
        "max_volume",
        "user_filled_qty",
        "profit",
        "per_unit_marginal",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "product": r.product,
                    "side": r.side,
                    "limit_price": r.limit_price,
                    "quantity": r.quantity,
                    "clearing_price": r.clearing_price,
                    "max_volume": r.max_volume,
                    "user_filled_qty": r.user_filled_qty,
                    "profit": r.profit,
                    "per_unit_marginal": r.per_unit_marginal,
                }
            )


def save_heatmap_png(
    prices: np.ndarray,
    qtys: np.ndarray,
    grid: np.ndarray,
    title: str,
    path: Path,
) -> None:
    """Save imshow heatmap: rows = limit price, columns = quantity."""

    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    data = np.ma.masked_invalid(grid)
    im = ax.imshow(data, aspect="auto", origin="lower", interpolation="nearest", cmap="viridis")
    ax.set_title(title)
    ax.set_xlabel("quantity")
    ax.set_ylabel("limit price")
    step_p = max(1, len(prices) // 10)
    step_q = max(1, len(qtys) // 10)
    ax.set_xticks(range(0, len(qtys), step_q))
    ax.set_xticklabels([str(qtys[i]) for i in range(0, len(qtys), step_q)], rotation=45, ha="right")
    ax.set_yticks(range(0, len(prices), step_p))
    ax.set_yticklabels([str(prices[i]) for i in range(0, len(prices), step_p)])
    fig.colorbar(im, ax=ax, label="profit")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def random_supplement_candidates(
    rng: np.random.Generator,
    n: int,
    price_lo: int,
    price_hi: int,
    qty_cap: int,
) -> list[tuple[OrderSide, int, int]]:
    """Optional uniform random (side, price, qty) pairs."""

    out: list[tuple[OrderSide, int, int]] = []
    for _ in range(n):
        side = OrderSide.BID if rng.random() < 0.5 else OrderSide.ASK
        price = int(rng.integers(price_lo, price_hi + 1))
        qty = int(rng.integers(1, qty_cap + 1))
        out.append((side, price, qty))
    return out


def evaluate_pairs(
    sim: ClearingSimulator,
    params: ProductParams,
    pairs: Sequence[tuple[OrderSide, int, int]],
) -> list[CandidateRow]:
    """Evaluate explicit list of (side, price, qty)."""

    rows: list[CandidateRow] = []
    for side, price, qty in pairs:
        out = sim.simulate(side, price, qty)
        rows.append(
            CandidateRow(
                product=params.name,
                side=side.value,
                limit_price=price,
                quantity=qty,
                clearing_price=out.clearing_price,
                max_volume=out.max_volume,
                user_filled_qty=out.user_filled_qty,
                profit=out.profit,
                per_unit_marginal=out.per_unit_marginal,
            )
        )
    return rows


def merge_dedupe_rows(rows: Sequence[CandidateRow]) -> list[CandidateRow]:
    """Keep highest profit if duplicate (product, side, price, qty)."""

    key = lambda r: (r.product, r.side, r.limit_price, r.quantity)
    best: dict[tuple[str, str, int, int], CandidateRow] = {}
    for r in rows:
        k = key(r)
        if k not in best or r.profit > best[k].profit:
            best[k] = r
    return sorted(best.values(), key=lambda r: r.profit, reverse=True)
