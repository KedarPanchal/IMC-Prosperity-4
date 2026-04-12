from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

DEFAULT_LIMIT = 50
POSITION_LIMITS: Dict[str, int] = {
    "EMERALDS": 80,
    "TOMATOES": 80,
}

SKEW_LIGHT = 0.25
SKEW_HEAVY = 0.60

EMERALD_FAIR_VALUE = 10000
EMERALD_TAKE_EDGE = 2

# (offset_from_fair, allocation_fraction) — last level absorbs rounding remainder
EMERALD_LADDER = [
    (4, 0.30),   # 9996 / 10004
    (6, 0.40),   # 9994 / 10006
    (8, 0.30),   # 9992 / 10008
]

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

                skew = 0
                if state.timestamp >= EMERALD_SESSION_END:
                    if pos > 0:
                        skew = -3
                    elif pos < 0:
                        skew = 3
                elif pos_frac > SKEW_HEAVY:
                    skew = -2
                elif pos_frac > SKEW_LIGHT:
                    skew = -1
                elif pos_frac < -SKEW_HEAVY:
                    skew = 2
                elif pos_frac < -SKEW_LIGHT:
                    skew = 1

                total_buy = max_buy
                total_sell = max_sell

                for i, (offset, alloc) in enumerate(EMERALD_LADDER):
                    bid_px = EMERALD_FAIR_VALUE - offset + skew
                    ask_px = EMERALD_FAIR_VALUE + offset + skew

                    if ask_px <= bid_px:
                        continue

                    if i == len(EMERALD_LADDER) - 1:
                        buy_qty = max_buy
                        sell_qty = max_sell
                    else:
                        buy_qty = clamp(int(total_buy * alloc), 0, max_buy)
                        sell_qty = clamp(int(total_sell * alloc), 0, max_sell)

                    if buy_qty > 0:
                        orders.append(Order(product, bid_px, buy_qty))
                        max_buy -= buy_qty
                    if sell_qty > 0:
                        orders.append(Order(product, ask_px, -sell_qty))
                        max_sell -= sell_qty

                result[product] = orders
                continue

            # ── Generic book-relative MM for all other products ──
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