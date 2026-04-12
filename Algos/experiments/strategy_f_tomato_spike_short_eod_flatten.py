"""
Experiment F: Tomatoes — short-only on spikes, cover only in end window.

- Uses full position limit on the short side when a spike fires (wall mid jumps up).
- No buys / no long inventory before the cover window (no bids, no lift asks).
- After TOMATO_COVER_START_MS, aggressively buy to flatten toward flat.

Emeralds: same MM as production baseline.

Tunable: SPIKE_WM_DELTA, TOMATO_COVER_START_MS (set from official session length when known).
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, Optional
import json

DEFAULT_LIMIT = 50
POSITION_LIMITS: Dict[str, int] = {
    "EMERALDS": 80,
    "TOMATOES": 80,
}

SKEW_LIGHT = 0.25
SKEW_HEAVY = 0.60

EMERALD_FAIR_VALUE = 10000
EMERALD_TAKE_EDGE = 1

# Tomato experiment
SPIKE_WM_DELTA = 2.0
TOMATO_COVER_START_MS = 190_000


def best_bid_ask(od: OrderDepth):
    bb = max(od.buy_orders.keys()) if od.buy_orders else None
    ba = min(od.sell_orders.keys()) if od.sell_orders else None
    return bb, ba


def wall_mid(od: OrderDepth) -> Optional[float]:
    if not od.buy_orders or not od.sell_orders:
        return None
    bid_wall = max(od.buy_orders, key=lambda p: od.buy_orders[p])
    ask_wall = max(od.sell_orders.keys(), key=lambda p: abs(od.sell_orders[p]))
    return (bid_wall + ask_wall) / 2


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def get_limit(product: str) -> int:
    return POSITION_LIMITS.get(product, DEFAULT_LIMIT)


class Trader:

    def run(self, state: TradingState):

        result: Dict[str, list] = {}
        trader_state: Dict = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except (json.JSONDecodeError, TypeError):
                trader_state = {}

        prev_tom_wm = trader_state.get("tom_wm")

        for product in state.order_depths:
            od = state.order_depths[product]
            pos = state.position.get(product, 0)
            limit = get_limit(product)
            bid, ask = best_bid_ask(od)

            if bid is None or ask is None:
                result[product] = []
                continue

            orders = []
            max_buy = limit - pos
            max_sell = limit + pos
            pos_frac = pos / limit if limit > 0 else 0

            if product == "EMERALDS":
                buy_take_px = EMERALD_FAIR_VALUE - EMERALD_TAKE_EDGE
                sell_take_px = EMERALD_FAIR_VALUE + EMERALD_TAKE_EDGE

                for px in sorted(od.sell_orders):
                    if px > buy_take_px or max_buy <= 0:
                        break
                    qty = min(max_buy, -od.sell_orders[px])
                    if qty > 0:
                        orders.append(Order(product, px, qty))
                        max_buy -= qty

                for px in sorted(od.buy_orders, reverse=True):
                    if px < sell_take_px or max_sell <= 0:
                        break
                    qty = min(max_sell, od.buy_orders[px])
                    if qty > 0:
                        orders.append(Order(product, px, -qty))
                        max_sell -= qty

                bid_offset = 7
                ask_offset = 7

                if pos_frac > SKEW_HEAVY:
                    bid_offset = 8
                    ask_offset = 6
                elif pos_frac > SKEW_LIGHT:
                    ask_offset = 6
                elif pos_frac < -SKEW_HEAVY:
                    bid_offset = 6
                    ask_offset = 8
                elif pos_frac < -SKEW_LIGHT:
                    bid_offset = 6

                l1_bid = EMERALD_FAIR_VALUE - bid_offset
                l1_ask = EMERALD_FAIR_VALUE + ask_offset

                if l1_ask > l1_bid:
                    l1_buy = clamp(int(max_buy * 0.6), 0, max_buy)
                    l1_sell = clamp(int(max_sell * 0.6), 0, max_sell)

                    if l1_buy > 0:
                        orders.append(Order(product, l1_bid, l1_buy))
                        max_buy -= l1_buy
                    if l1_sell > 0:
                        orders.append(Order(product, l1_ask, -l1_sell))
                        max_sell -= l1_sell

                    if max_buy > 0:
                        orders.append(Order(product, l1_bid - 1, max_buy))
                    if max_sell > 0:
                        orders.append(Order(product, l1_ask + 1, -max_sell))

                result[product] = orders
                continue

            if product == "TOMATOES":
                wm = wall_mid(od)
                covering = state.timestamp >= TOMATO_COVER_START_MS

                if covering:
                    for px in sorted(od.sell_orders):
                        if max_buy <= 0:
                            break
                        qty = min(max_buy, -od.sell_orders[px])
                        if qty > 0:
                            orders.append(Order(product, px, qty))
                            max_buy -= qty

                    if pos < 0 and max_buy > 0 and ask > bid:
                        aggressive_bid = ask - 1
                        if aggressive_bid < ask:
                            orders.append(Order(product, aggressive_bid, max_buy))

                    if pos > 0 and max_sell > 0:
                        for px in sorted(od.buy_orders, reverse=True):
                            if max_sell <= 0:
                                break
                            qty = min(max_sell, od.buy_orders[px])
                            if qty > 0:
                                orders.append(Order(product, px, -qty))
                                max_sell -= qty
                else:
                    if pos > 0 and max_sell > 0:
                        for px in sorted(od.buy_orders, reverse=True):
                            if max_sell <= 0:
                                break
                            qty = min(max_sell, od.buy_orders[px])
                            if qty > 0:
                                orders.append(Order(product, px, -qty))
                                max_sell -= qty

                    spike = (
                        prev_tom_wm is not None
                        and wm is not None
                        and (wm - prev_tom_wm) >= SPIKE_WM_DELTA
                    )
                    if spike:
                        ms = limit + pos
                        for px in sorted(od.buy_orders, reverse=True):
                            if ms <= 0:
                                break
                            qty = min(ms, od.buy_orders[px])
                            if qty > 0:
                                orders.append(Order(product, px, -qty))
                                ms -= qty
                        if ms > 0 and bid is not None:
                            orders.append(Order(product, bid, -ms))

                if wm is not None:
                    trader_state["tom_wm"] = wm

                result[product] = orders
                continue

            buy_edge = 1
            sell_edge = 1

            if pos_frac > SKEW_HEAVY:
                buy_edge = 0
                sell_edge = 2
            elif pos_frac > SKEW_LIGHT:
                sell_edge = 2
            elif pos_frac < -SKEW_HEAVY:
                buy_edge = 2
                sell_edge = 0
            elif pos_frac < -SKEW_LIGHT:
                buy_edge = 2

            our_bid = bid + buy_edge
            our_ask = ask - sell_edge

            if our_ask > our_bid:
                l1_buy = clamp(int(max_buy * 0.6), 0, max_buy)
                l1_sell = clamp(int(max_sell * 0.6), 0, max_sell)

                if l1_buy > 0:
                    orders.append(Order(product, our_bid, l1_buy))
                if l1_sell > 0:
                    orders.append(Order(product, our_ask, -l1_sell))

                l2_buy = max_buy - l1_buy
                l2_sell = max_sell - l1_sell

                if l2_buy > 0:
                    orders.append(Order(product, our_bid - 1, l2_buy))
                if l2_sell > 0:
                    orders.append(Order(product, our_ask + 1, -l2_sell))

            result[product] = orders

        return result, 0, json.dumps(trader_state)
