"""
Uniform-price call auction with max-volume then highest-P tie-break.

Casual: Figure out clearing price and how much you fill.
Formal: For candidate clearing prices P, compute V(P)=min(D(P),S(P)), pick P* in
argmax V with maximum P; then allocate trade volume V(P*) on your side
(price priority, then time; you are last at your price level).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class OrderSide(str, Enum):
    """Whether you submit a limit bid (buy) or limit ask (sell / short)."""

    BID = "bid"
    ASK = "ask"


@dataclass(frozen=True)
class ProductParams:
    """
    Post-auction buyback anchor and per-unit fees on the buyback leg.

    Casual: Numbers the merchant uses after the auction.
    Formal: Long profit uses anchor - P minus fee_long; short uses P - anchor minus fee_short.
    """

    name: str
    buyback_anchor: float
    fee_long: float
    fee_short: float


@dataclass(frozen=True)
class ClearingOutcome:
    """Result of one simulated (side, price, qty) submission."""

    clearing_price: float | None
    max_volume: int
    user_filled_qty: int
    profit: float
    per_unit_marginal: float


def _merge_volume(levels: dict[int, int], price: int, extra: int) -> dict[int, int]:
    """Return a copy of volume-by-price with extra added at `price`."""

    out = dict(levels)
    out[price] = out.get(price, 0) + extra
    return out


def _demand_at_p(bids: dict[int, int], p: int) -> int:
    """Total bid volume for bids with price >= p."""

    return sum(vol for price, vol in bids.items() if price >= p)


def _supply_at_p(asks: dict[int, int], p: int) -> int:
    """Total ask volume for asks with price <= p."""

    return sum(vol for price, vol in asks.items() if price <= p)


def _candidate_prices(
    bids: dict[int, int],
    asks: dict[int, int],
    user_price: int,
) -> list[int]:
    """Enumerate integer clearing prices to consider (ladder + user + full range)."""

    prices: set[int] = set(bids) | set(asks) | {user_price}
    if not prices:
        return [user_price]
    lo, hi = min(prices), max(prices)
    # Volume step-functions change at ladder; scanning every integer in [lo, hi] is safe.
    return list(range(lo, hi + 1))


def _volume_curve(
    bids: dict[int, int],
    asks: dict[int, int],
    user_side: OrderSide,
    user_price: int,
    user_qty: int,
) -> dict[int, int]:
    """V(P) = min(D(P), S(P)) including the user's order."""

    if user_side is OrderSide.BID:
        bids = _merge_volume(bids, user_price, user_qty)
    else:
        asks = _merge_volume(asks, user_price, user_qty)

    candidates = _candidate_prices(bids, asks, user_price)
    return {p: min(_demand_at_p(bids, p), _supply_at_p(asks, p)) for p in candidates}


def _pick_clearing_price(v_curve: dict[int, int]) -> tuple[float | None, int]:
    """
    Maximize V(P), then tie-break to highest P.

    Returns (P_star, max_v) or (None, 0) if no positive volume.
    """

    if not v_curve:
        return None, 0
    max_v = max(v_curve.values())
    if max_v <= 0:
        return None, 0
    max_p = max(p for p, v in v_curve.items() if v == max_v)
    return float(max_p), max_v


def _build_buy_order_queue(
    resting_bids: dict[int, int],
    user_price: int,
    user_qty: int,
    p_star: int,
) -> list[tuple[int, int, bool]]:
    """
    Price priority: higher bid first. Time: resting before user at each price (user last).

    Only includes orders that participate at clearing price p_star (bid >= p_star).

    Returns list of (price, qty, is_user).
    """

    orders: list[tuple[int, int, bool]] = []
    for price, vol in resting_bids.items():
        if price >= p_star:
            orders.append((price, vol, False))
    if user_price >= p_star and user_qty > 0:
        orders.append((user_price, user_qty, True))
    # Sort: -price desc, then is_user False before True (resting first).
    orders.sort(key=lambda t: (-t[0], t[2]))
    return orders


def _build_sell_order_queue(
    resting_asks: dict[int, int],
    user_price: int,
    user_qty: int,
    p_star: int,
) -> list[tuple[int, int, bool]]:
    """
    Price priority: lower ask first. Time: resting before user (user last).

    Only includes asks with ask <= p_star.

    Returns list of (price, qty, is_user).
    """

    orders: list[tuple[int, int, bool]] = []
    for price, vol in resting_asks.items():
        if price <= p_star:
            orders.append((price, vol, False))
    if user_price <= p_star and user_qty > 0:
        orders.append((user_price, user_qty, True))
    orders.sort(key=lambda t: (t[0], t[2]))
    return orders


def _allocate_user_fill(
    queue: Iterable[tuple[int, int, bool]],
    total_trade: int,
) -> int:
    """Walk the queue in priority order; return how many units the user gets."""

    remain = total_trade
    user_fill = 0
    for _price, qty, is_user in queue:
        take = min(qty, remain)
        if is_user:
            user_fill += take
        remain -= take
        if remain <= 0:
            break
    return user_fill


class ClearingSimulator:
    """
    Frozen resting book + your last order; computes P*, fill, and profit.

    Casual: Plug in your order and see what happens.
    Formal: Encapsulates the Stackelberg follower mapping (clearing rule + rationing).
    """

    def __init__(
        self,
        resting_bids: dict[int, int],
        resting_asks: dict[int, int],
        params: ProductParams,
    ) -> None:
        self._resting_bids = resting_bids
        self._resting_asks = resting_asks
        self._params = params

    def simulate(
        self,
        side: OrderSide,
        user_price: int,
        user_qty: int,
    ) -> ClearingOutcome:
        """
        Run one simulation.

        Casual: Your side, price, size — get profit.
        Formal: Builds augmented book, computes V(P), P*, then marginal user fill
        on the active side; profit = q * per_unit(side, P*).
        """

        if user_qty <= 0:
            return ClearingOutcome(
                clearing_price=None,
                max_volume=0,
                user_filled_qty=0,
                profit=0.0,
                per_unit_marginal=0.0,
            )

        v_curve = _volume_curve(
            self._resting_bids,
            self._resting_asks,
            side,
            user_price,
            user_qty,
        )
        p_star, max_v = _pick_clearing_price(v_curve)
        if p_star is None or max_v <= 0:
            return ClearingOutcome(
                clearing_price=None,
                max_volume=0,
                user_filled_qty=0,
                profit=0.0,
                per_unit_marginal=0.0,
            )

        p_int = int(p_star)

        if side is OrderSide.BID:
            if user_price < p_int:
                # Not willing to participate at clearing.
                return ClearingOutcome(
                    clearing_price=p_star,
                    max_volume=max_v,
                    user_filled_qty=0,
                    profit=0.0,
                    per_unit_marginal=self._per_unit_long(p_int),
                )
            queue = _build_buy_order_queue(
                self._resting_bids,
                user_price,
                user_qty,
                p_int,
            )
            user_fill = _allocate_user_fill(queue, max_v)
            per_unit = self._per_unit_long(p_int)
        else:
            if user_price > p_int:
                return ClearingOutcome(
                    clearing_price=p_star,
                    max_volume=max_v,
                    user_filled_qty=0,
                    profit=0.0,
                    per_unit_marginal=self._per_unit_short(p_int),
                )
            queue = _build_sell_order_queue(
                self._resting_asks,
                user_price,
                user_qty,
                p_int,
            )
            user_fill = _allocate_user_fill(queue, max_v)
            per_unit = self._per_unit_short(p_int)

        profit = float(user_fill) * per_unit
        return ClearingOutcome(
            clearing_price=p_star,
            max_volume=max_v,
            user_filled_qty=user_fill,
            profit=profit,
            per_unit_marginal=per_unit,
        )

    def _per_unit_long(self, p: int) -> float:
        """Long: buy at P, sell at anchor; subtract fee on long."""

        return self._params.buyback_anchor - float(p) - self._params.fee_long

    def _per_unit_short(self, p: int) -> float:
        """Short: sell at P, cover at anchor; subtract fee on cover."""

        return float(p) - self._params.buyback_anchor - self._params.fee_short
