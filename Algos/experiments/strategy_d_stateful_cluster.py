from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

# Strategy D: Asymmetric offset with stateful fill tracking
# After a buy fill, sellers may be clustering — widen bid for 2 ticks to
# avoid stacking more long inventory. Uses traderData to persist state
# (last known position) between run() calls to detect fills.
# Expected impact: uncertain; experimental.

DEFAULT_LIMIT = 50
POSITION_LIMITS: Dict[str, int] = {
    "EMERALDS": 80,
    "TOMATOES": 80,
}

SKEW_LIGHT = 0.25
SKEW_HEAVY = 0.60

EMERALD_FAIR_VALUE = 10000
EMERALD_TAKE_EDGE = 2
EMERALD_SESSION_END = 180000
COOLDOWN_TICKS = 200


def best_bid_ask(od: OrderDepth):
    bb = max(od.buy_orders.keys())  if od.buy_orders  else None
    ba = min(od.sell_orders.keys()) if od.sell_orders else None
    return bb, ba

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def get_limit(product: str) -> int:
    return POSITION_LIMITS.get(product, DEFAULT_LIMIT)


class Trader:

    def run(self, state: TradingState):

        result = {}
        trader_state = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except (json.JSONDecodeError, TypeError):
                pass

        prev_em_pos = trader_state.get("em_pos", 0)
        last_buy_ts = trader_state.get("last_buy_ts", -99999)
        last_sell_ts = trader_state.get("last_sell_ts", -99999)

        for product in state.order_depths:
            od  = state.order_depths[product]
            pos = state.position.get(product, 0)
            limit = get_limit(product)
            bid, ask = best_bid_ask(od)

            if bid is None or ask is None:
                result[product] = []
                continue

            orders = []
            max_buy  = limit - pos
            max_sell = limit + pos
            pos_frac = pos / limit if limit > 0 else 0

            if product == "EMERALDS":
                em_delta = pos - prev_em_pos
                if em_delta > 0:
                    last_buy_ts = state.timestamp
                elif em_delta < 0:
                    last_sell_ts = state.timestamp

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

                recent_buy  = (state.timestamp - last_buy_ts) <= COOLDOWN_TICKS
                recent_sell = (state.timestamp - last_sell_ts) <= COOLDOWN_TICKS

                if state.timestamp >= EMERALD_SESSION_END:
                    if pos > 0:
                        bid_offset = 9
                        ask_offset = 4
                    elif pos < 0:
                        bid_offset = 4
                        ask_offset = 9
                elif pos_frac > SKEW_HEAVY:
                    bid_offset = 8
                    ask_offset = 6
                elif pos_frac > SKEW_LIGHT:
                    ask_offset = 6
                elif pos_frac < -SKEW_HEAVY:
                    bid_offset = 6
                    ask_offset = 8
                elif pos_frac < -SKEW_LIGHT:
                    bid_offset = 6

                if recent_buy and not recent_sell:
                    bid_offset = max(bid_offset, 8)
                elif recent_sell and not recent_buy:
                    ask_offset = max(ask_offset, 8)

                l1_bid = EMERALD_FAIR_VALUE - bid_offset
                l1_ask = EMERALD_FAIR_VALUE + ask_offset

                if l1_ask > l1_bid:
                    l1_buy  = clamp(int(max_buy * 0.6), 0, max_buy)
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

                trader_state["em_pos"] = pos
                trader_state["last_buy_ts"] = last_buy_ts
                trader_state["last_sell_ts"] = last_sell_ts

                result[product] = orders
                continue

            buy_edge  = 1
            sell_edge = 1

            if pos_frac > SKEW_HEAVY:
                buy_edge = 0; sell_edge = 2
            elif pos_frac > SKEW_LIGHT:
                sell_edge = 2
            elif pos_frac < -SKEW_HEAVY:
                buy_edge = 2; sell_edge = 0
            elif pos_frac < -SKEW_LIGHT:
                buy_edge = 2

            our_bid = bid + buy_edge
            our_ask = ask - sell_edge

            if our_ask > our_bid:
                l1_buy  = clamp(int(max_buy * 0.6), 0, max_buy)
                l1_sell = clamp(int(max_sell * 0.6), 0, max_sell)

                if l1_buy > 0:
                    orders.append(Order(product, our_bid, l1_buy))
                if l1_sell > 0:
                    orders.append(Order(product, our_ask, -l1_sell))

                l2_buy  = max_buy - l1_buy
                l2_sell = max_sell - l1_sell

                if l2_buy > 0:
                    orders.append(Order(product, our_bid - 1, l2_buy))
                if l2_sell > 0:
                    orders.append(Order(product, our_ask + 1, -l2_sell))

            result[product] = orders

        return result, 0, json.dumps(trader_state)
