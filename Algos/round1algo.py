from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json

POSITION_LIMITS: Dict[str, int] = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}
DEFAULT_LIMIT = 50

# osmium: known fair value, sweep + MM
OSMIUM_FAIR = 10000

# pepper root: signal-driven trend following
PEPPER_FAST = 12
PEPPER_SLOW = 48
PEPPER_VEL_WINDOW = 6
PEPPER_ACC_WINDOW = 6
PEPPER_FV_LOOKAHEAD = 10
PEPPER_INV_K = 0.07
PEPPER_BASE_EDGE = 2.0
PEPPER_MM_CAP_FRAC = 0.20
PEPPER_DIR_CAP_FRAC = 0.95
PEPPER_STRONG_SIGNAL = 10.0
PEPPER_MED_SIGNAL = 5.0
PEPPER_CROSS_SIGNAL = 16.0
PEPPER_MAX_HIST = 160

# pepper SMA drawdown overlay (vs mid history)
PEPPER_SMA_PERIOD = 32
PEPPER_SMA_POS_MIN_FRAC = 0.08
PEPPER_SMA_BUFFER = 0.5

# signal regression coefficients
REG_DRIFT = 0.75
REG_VEL = 0.25
REG_ACC = 0.08
REG_IMB = 1.1
REG_SPREAD = -0.15

# stable product skew
SKEW_LIGHT = 0.25
SKEW_HEAVY = 0.60


def best_bid_ask(od: OrderDepth):
    bb = max(od.buy_orders.keys()) if od.buy_orders else None
    ba = min(od.sell_orders.keys()) if od.sell_orders else None
    return bb, ba

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def get_limit(product: str) -> int:
    return POSITION_LIMITS.get(product, DEFAULT_LIMIT)

def ema(values, span):
    if not values:
        return 0.0
    alpha = 2.0 / (span + 1.0)
    out = values[0]
    for x in values[1:]:
        out = alpha * x + (1 - alpha) * out
    return out

def sma(values, n):
    if len(values) < n or n <= 0:
        return None
    window = values[-n:]
    return sum(window) / float(n)

def depth_imbalance(od: OrderDepth) -> float:
    bid_vol = sum(qty for qty in od.buy_orders.values())
    ask_vol = sum(-qty for qty in od.sell_orders.values())
    total = bid_vol + ask_vol
    if total <= 0:
        return 0.0
    return (bid_vol - ask_vol) / total


class Trader:

    def run(self, state: TradingState):
        memory = json.loads(state.traderData) if state.traderData else {}
        result: Dict[str, List[Order]] = {}

        for product, od in state.order_depths.items():
            pos = state.position.get(product, 0)
            limit = get_limit(product)
            bid, ask = best_bid_ask(od)

            if bid is None or ask is None:
                result[product] = []
                continue

            mid = (bid + ask) / 2.0
            spread = ask - bid

            hist = memory.get(product, [])
            hist.append(mid)
            if len(hist) > PEPPER_MAX_HIST:
                hist = hist[-PEPPER_MAX_HIST:]
            memory[product] = hist

            if product == "ASH_COATED_OSMIUM":
                orders = self._trade_osmium(product, od, pos, limit, bid, ask)
            elif product == "INTARIAN_PEPPER_ROOT":
                orders = self._trade_pepper(product, od, pos, limit, bid, ask, spread, hist)
            else:
                # unknown product: default MM
                orders = self._trade_default(product, od, pos, limit, bid, ask)

            result[product] = orders

        return result, 0, json.dumps(memory)


    def _trade_osmium(self, product, od, pos, limit, bid, ask):
        """stable product: strict sweep below/above fair + fair-anchored MM"""
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos

        # sweep asks STRICTLY below fair (not at fair — that's zero edge)
        for px in sorted(od.sell_orders.keys()):
            if px < OSMIUM_FAIR and max_buy > 0:
                qty = min(max_buy, -od.sell_orders[px])
                if qty > 0:
                    orders.append(Order(product, px, qty))
                    max_buy -= qty
            else:
                break

        # sweep bids STRICTLY above fair
        for px in sorted(od.buy_orders.keys(), reverse=True):
            if px > OSMIUM_FAIR and max_sell > 0:
                qty = min(max_sell, od.buy_orders[px])
                if qty > 0:
                    orders.append(Order(product, px, -qty))
                    max_sell -= qty
            else:
                break

        # passive MM with position skew, anchored to fair value
        pos_frac = pos / limit if limit else 0.0
        buy_edge = 1
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

        # anchor to fair: never buy above fair-1, never sell below fair+1
        our_bid = min(our_bid, OSMIUM_FAIR - 1)
        our_ask = max(our_ask, OSMIUM_FAIR + 1)

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

        return orders


    def _trade_pepper(self, product, od, pos, limit, bid, ask, spread, hist):
        """trending product: signal-driven entries + reservation price quoting"""
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos
        pos_frac = pos / limit if limit else 0.0

        # compute signals
        fast = ema(hist[-PEPPER_FAST:], PEPPER_FAST) if len(hist) >= 2 else hist[-1]
        slow = ema(hist[-PEPPER_SLOW:], PEPPER_SLOW) if len(hist) >= 2 else hist[-1]

        vel = 0.0
        if len(hist) > PEPPER_VEL_WINDOW:
            vel = hist[-1] - hist[-1 - PEPPER_VEL_WINDOW]

        prev_vel = 0.0
        if len(hist) > PEPPER_VEL_WINDOW + PEPPER_ACC_WINDOW:
            prev_vel = hist[-1 - PEPPER_VEL_WINDOW] - hist[-1 - PEPPER_VEL_WINDOW - PEPPER_ACC_WINDOW]

        acc = vel - prev_vel
        imb = depth_imbalance(od)
        drift = fast - slow

        # reservation price: projected fair value adjusted for inventory
        fair = slow + drift * PEPPER_FV_LOOKAHEAD
        reservation = fair - PEPPER_INV_K * pos

        # composite signal
        signal = (
            REG_DRIFT * drift
            + REG_VEL * vel
            + REG_ACC * acc
            + REG_IMB * imb
            + REG_SPREAD * spread
        )
        abs_signal = abs(signal)
        bullish = signal > 0
        bearish = signal < 0

        dir_cap = int(limit * PEPPER_DIR_CAP_FRAC)
        mm_cap = int(limit * PEPPER_MM_CAP_FRAC)

        mid = hist[-1]
        sma_val = sma(hist, PEPPER_SMA_PERIOD)
        pos_min = max(5, int(limit * PEPPER_SMA_POS_MIN_FRAC))
        protect_long = (
            sma_val is not None
            and pos >= pos_min
            and mid < sma_val - PEPPER_SMA_BUFFER
        )
        protect_short = (
            sma_val is not None
            and pos <= -pos_min
            and mid > sma_val + PEPPER_SMA_BUFFER
        )

        # dynamic threshold for spread crossing
        take_threshold = 3.0 + 0.25 * max(0, spread - 12)
        if abs_signal < PEPPER_MED_SIGNAL:
            take_threshold += 1.5
        elif abs_signal > PEPPER_STRONG_SIGNAL:
            take_threshold -= 0.5

        # size scales with conviction
        if abs_signal > PEPPER_CROSS_SIGNAL:
            take_size = int(limit * 0.35)
            quote_size = int(limit * 0.22)
        elif abs_signal > PEPPER_STRONG_SIGNAL:
            take_size = int(limit * 0.25)
            quote_size = int(limit * 0.18)
        elif abs_signal > PEPPER_MED_SIGNAL:
            take_size = int(limit * 0.18)
            quote_size = int(limit * 0.14)
        else:
            take_size = int(limit * 0.12)
            quote_size = int(limit * 0.10)

        take_size = max(6, take_size)
        quote_size = max(5, quote_size)

        # aggressive crossing on strong signals
        if (
            bullish
            and not protect_long
            and ask <= reservation - take_threshold
            and pos < dir_cap
            and max_buy > 0
        ):
            qty = min(max_buy, take_size)
            orders.append(Order(product, ask, qty))
            max_buy -= qty
        elif (
            bearish
            and not protect_short
            and bid >= reservation + take_threshold
            and pos > -dir_cap
            and max_sell > 0
        ):
            qty = min(max_sell, take_size)
            orders.append(Order(product, bid, -qty))
            max_sell -= qty
        else:
            # momentum cross on extreme signals
            if (
                bullish
                and not protect_long
                and abs_signal > PEPPER_CROSS_SIGNAL
                and pos < dir_cap
                and max_buy > 0
            ):
                qty = min(max_buy, max(6, int(limit * 0.16)))
                orders.append(Order(product, ask, qty))
                max_buy -= qty
            elif (
                bearish
                and not protect_short
                and abs_signal > PEPPER_CROSS_SIGNAL
                and pos > -dir_cap
                and max_sell > 0
            ):
                qty = min(max_sell, max(6, int(limit * 0.16)))
                orders.append(Order(product, bid, -qty))
                max_sell -= qty

        # quote around reservation price
        edge = PEPPER_BASE_EDGE + 0.20 * max(0, spread - 12)
        if abs_signal < PEPPER_MED_SIGNAL:
            edge += 0.5
        elif abs_signal > PEPPER_STRONG_SIGNAL:
            edge -= 0.5

        edge_i = clamp(int(round(edge)), 1, 4)
        quote_bid = min(bid + 1, int(round(reservation - edge_i)))
        quote_ask = max(ask - 1, int(round(reservation + edge_i)))

        # directional leaning
        if bullish:
            quote_bid = min(ask - 1, quote_bid + 1)
            if pos_frac > 0.55:
                quote_ask = max(bid + 1, quote_ask)
            else:
                quote_ask = max(bid + 1, quote_ask + 1)
        elif bearish:
            quote_ask = max(bid + 1, quote_ask - 1)
            if pos_frac < -0.55:
                quote_bid = min(ask - 1, quote_bid)
            else:
                quote_bid = min(ask - 1, quote_bid - 1)

        # inventory safety at extremes
        if pos > mm_cap:
            quote_bid = min(quote_bid, bid)
            quote_ask = max(bid + 1, quote_ask - 1)
        elif pos < -mm_cap:
            quote_ask = max(quote_ask, ask)
            quote_bid = min(ask - 1, quote_bid + 1)

        # SMA: mid vs average against position -> lean quotes toward flattening
        if protect_long:
            quote_bid = min(quote_bid, bid)
            quote_ask = max(bid + 1, quote_ask - 1)
        elif protect_short:
            quote_ask = max(quote_ask, ask)
            quote_bid = min(ask - 1, quote_bid + 1)

        quote_bid = min(quote_bid, ask - 1)
        quote_ask = max(quote_ask, bid + 1)

        if quote_ask > quote_bid:
            buy_size = clamp(min(max_buy, quote_size), 0, max_buy)
            sell_size = clamp(min(max_sell, quote_size), 0, max_sell)

            # bias size toward signal direction
            if bullish and abs_signal > PEPPER_MED_SIGNAL:
                buy_size = clamp(min(max_buy, int(quote_size * 1.5)), 0, max_buy)
                sell_size = clamp(min(max_sell, max(3, int(quote_size * 0.6))), 0, max_sell)
            elif bearish and abs_signal > PEPPER_MED_SIGNAL:
                sell_size = clamp(min(max_sell, int(quote_size * 1.5)), 0, max_sell)
                buy_size = clamp(min(max_buy, max(3, int(quote_size * 0.6))), 0, max_buy)

            if protect_long:
                buy_size = 0
                sell_size = clamp(min(max_sell, int(quote_size * 1.6)), 0, max_sell)
            elif protect_short:
                sell_size = 0
                buy_size = clamp(min(max_buy, int(quote_size * 1.6)), 0, max_buy)

            if buy_size > 0 and pos < dir_cap:
                orders.append(Order(product, quote_bid, buy_size))
            if sell_size > 0 and pos > -dir_cap:
                orders.append(Order(product, quote_ask, -sell_size))

            # L2 quotes
            l2_buy = clamp(min(max_buy, max(0, int(quote_size * 0.65))), 0, max_buy)
            l2_sell = clamp(min(max_sell, max(0, int(quote_size * 0.65))), 0, max_sell)

            if l2_buy > 0 and not protect_long and quote_bid - 1 > 0 and pos < dir_cap:
                orders.append(Order(product, quote_bid - 1, l2_buy))
            if l2_sell > 0 and not protect_short and pos > -dir_cap:
                orders.append(Order(product, quote_ask + 1, -l2_sell))

        return orders


    def _trade_default(self, product, od, pos, limit, bid, ask):
        """fallback MM for unknown products"""
        orders = []
        max_buy = limit - pos
        max_sell = limit + pos
        pos_frac = pos / limit if limit else 0.0

        buy_edge = 1
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

        return orders