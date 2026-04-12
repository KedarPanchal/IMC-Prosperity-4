from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

# Strategy E: Probe offset 8 at L1
# Quote at 9992/10008 (AT the NPC book) instead of 9993/10007 (inside it).
# If the sim still gives us ~29 fills, we gain +1 tick per fill = ~14% more PnL.
# HIGH RISK: if NPC orders have queue priority at 9992/10008, we lose most fills.
# Test in a throwaway submission first.
# Expected impact: +147 if fills hold, catastrophic if fills drop to near-zero.

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

                bid_offset = 8
                ask_offset = 8

                if state.timestamp >= EMERALD_SESSION_END:
                    if pos > 0:
                        bid_offset = 10
                        ask_offset = 5
                    elif pos < 0:
                        bid_offset = 5
                        ask_offset = 10
                elif pos_frac > SKEW_HEAVY:
                    bid_offset = 9
                    ask_offset = 7
                elif pos_frac > SKEW_LIGHT:
                    ask_offset = 7
                elif pos_frac < -SKEW_HEAVY:
                    bid_offset = 7
                    ask_offset = 9
                elif pos_frac < -SKEW_LIGHT:
                    bid_offset = 7

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

        return result, 0, ""