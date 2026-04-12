from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

# Strategy C: Position-aware take for emergency flattening
# When heavily inventoried (>50% of limit), take 10000-touch liquidity to flatten.
# ~300 touch events per session last only 1 tick each — use them as emergency valves.
# Selling at 10000 gives 0 edge vs fair, so only fire when inventory is dangerous.
# Expected impact: small positive; prevents worst-case inventory blowouts.

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
EMERALD_EMERGENCY_FRAC = 0.50


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
                emergency_long  = pos_frac > EMERALD_EMERGENCY_FRAC
                emergency_short = pos_frac < -EMERALD_EMERGENCY_FRAC

                if emergency_long:
                    sell_take_threshold = EMERALD_FAIR_VALUE
                else:
                    sell_take_threshold = EMERALD_FAIR_VALUE + EMERALD_TAKE_EDGE

                if emergency_short:
                    buy_take_threshold = EMERALD_FAIR_VALUE
                else:
                    buy_take_threshold = EMERALD_FAIR_VALUE - EMERALD_TAKE_EDGE

                for px in sorted(od.sell_orders):
                    if px > buy_take_threshold or max_buy <= 0:
                        break
                    qty = min(max_buy, -od.sell_orders[px])
                    if qty > 0:
                        orders.append(Order(product, px, qty))
                        max_buy -= qty

                for px in sorted(od.buy_orders, reverse=True):
                    if px < sell_take_threshold or max_sell <= 0:
                        break
                    qty = min(max_sell, od.buy_orders[px])
                    if qty > 0:
                        orders.append(Order(product, px, -qty))
                        max_sell -= qty

                bid_offset = 7
                ask_offset = 7

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
