from datamodel import Order, TradingState
from typing import Dict, List, Optional
import json
import math


class Trader:
    """
    Round 2 v3.4 - osmium expansion build

    Philosophy:
    - Keep the proven carry engine in INTARIAN_PEPPER_ROOT.
    - Add a very small roots micro-trading overlay that clips local pops and rebuys local dips
      without letting the book drift far from long.
    - Keep ASH_COATED_OSMIUM as incremental alpha, not the main risk source.
    """

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    MAF_BID = 12000

    # ---------- Pepper Root ----------
    PEPPER_SLOPE = 0.001
    PEPPER_INTERCEPT_ALPHA = 0.18
    # The live run appears to end around 99,900; keep the old far-out unwind behavior so we hold carry.
    PEPPER_UNWIND_START = 820000.0
    PEPPER_FORCE_FLAT = 965000.0
    PEPPER_EARLY_PUSH_END = 7500.0
    PEPPER_MAX_CROSS = 32
    PEPPER_MAX_PASSIVE = 30
    PEPPER_TAKE_MARGIN = 1.15
    PEPPER_SELL_MARGIN = 1.05
    # Small roots HFT/scalp overlay. Intentionally tiny so it cannot overpower carry.
    PEPPER_SCALP_MIN_CORE = 65
    PEPPER_SCALP_SELL_EDGE = 1.4
    PEPPER_SCALP_BUY_EDGE = 1.0
    PEPPER_SCALP_UNIT = 8
    PEPPER_SCALP_MAX_INV = 12

    # ---------- Osmium ----------
    OSMIUM_DEFAULT_FAIR = 10000.0
    OSMIUM_MEAN_ALPHA = 0.08
    OSMIUM_VAR_ALPHA = 0.10
    OSMIUM_IMBALANCE_WEIGHT = 1.0
    OSMIUM_ENTRY_Z = 0.78
    OSMIUM_EXIT_Z = 0.18
    OSMIUM_TAKE_Z = 2.10
    OSMIUM_TARGET_SCALE = 30.0
    OSMIUM_MAX_TARGET = 76
    OSMIUM_MAX_CROSS = 8
    OSMIUM_MAX_PASSIVE = 18
    OSMIUM_INV_SKEW = 0.30

    def run(self, state: TradingState):
        mem = self._load_state(state.traderData)
        self._maybe_reset_for_new_day(state, mem)

        mem.setdefault("pepper_intercept", None)
        mem.setdefault("osmium_mu", self.OSMIUM_DEFAULT_FAIR)
        mem.setdefault("osmium_var", 16.0)

        orders: Dict[str, List[Order]] = {}
        for product in state.order_depths:
            if product == "INTARIAN_PEPPER_ROOT":
                orders[product] = self.trade_pepper(product, state, mem)
            elif product == "ASH_COATED_OSMIUM":
                orders[product] = self.trade_osmium(product, state, mem)

        mem["last_timestamp"] = int(getattr(state, "timestamp", 0))
        trader_data = json.dumps(mem, separators=(",", ":"))
        conversions = 0
        return orders, conversions, trader_data

    # ========================= Pepper Root =========================

    def trade_pepper(self, product: str, state: TradingState, mem: dict) -> List[Order]:
        depth = state.order_depths[product]
        pos = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        out: List[Order] = []

        bb = self.best_bid(depth)
        ba = self.best_ask(depth)
        mid = self.mid_price(depth)
        if mid is None:
            return out

        t = float(getattr(state, "timestamp", 0))
        current_fair_obs = mid - self.PEPPER_SLOPE * t
        prev = mem.get("pepper_intercept")
        intercept = current_fair_obs if prev is None else ((1.0 - self.PEPPER_INTERCEPT_ALPHA) * float(prev) + self.PEPPER_INTERCEPT_ALPHA * current_fair_obs)
        mem["pepper_intercept"] = intercept

        spot_fair = intercept + self.PEPPER_SLOPE * t
        liquidation_ts = max(t, self.PEPPER_UNWIND_START)
        carry_fair = intercept + self.PEPPER_SLOPE * liquidation_ts
        target = self.pepper_target_position(t, limit)

        # 1) Aggressive accumulation early. Once the edge is known, time-underweight is the main leak.
        if ba is not None and pos < target:
            ask_avail = max(0, -depth.sell_orders.get(ba, 0))
            urgency = target - pos
            edge = carry_fair - ba
            very_early = t <= self.PEPPER_EARLY_PUSH_END
            if edge >= self.PEPPER_TAKE_MARGIN or (very_early and urgency >= 3) or urgency >= 16:
                qty = min(target - pos, ask_avail, self.PEPPER_MAX_CROSS if very_early else max(10, self.PEPPER_MAX_CROSS - 8))
                if qty > 0:
                    out.append(Order(product, ba, qty))
                    pos += qty

        # 2) Optional one-level reach if we're still well under target and the next ask is cheap enough.
        if ba is not None and pos < target and depth.sell_orders:
            ask_prices = sorted(depth.sell_orders.keys())
            if len(ask_prices) >= 2:
                a2 = ask_prices[1]
                ask2_avail = max(0, -depth.sell_orders.get(a2, 0))
                urgency = target - pos
                if urgency >= 10 and a2 <= carry_fair - 0.15:
                    qty = min(target - pos, ask2_avail, max(0, self.PEPPER_MAX_CROSS // 2))
                    if qty > 0:
                        out.append(Order(product, a2, qty))
                        pos += qty

        # 3) Only sell if truly over target / late. Avoid churn while roots is the carry engine.
        if bb is not None and pos > target:
            bid_avail = max(0, depth.buy_orders.get(bb, 0))
            rich_now = bb - spot_fair
            late = t >= self.PEPPER_UNWIND_START
            over = pos - target
            if late or rich_now >= self.PEPPER_SELL_MARGIN + (0.15 if over < 8 else 0.0):
                qty = min(over, bid_avail, self.PEPPER_MAX_CROSS)
                if qty > 0:
                    out.append(Order(product, bb, -qty))
                    pos -= qty

        # 3b) Tiny roots micro-trading overlay.
        # Only operate once we already have a healthy long core and only in small clips.
        # Goal: sell a few units into local richness, rebuy a few on local weakness, while
        # staying broadly long for carry.
        if t < self.PEPPER_UNWIND_START and bb is not None and ba is not None:
            scalp_shortfall = max(0, limit - pos)
            scalp_excess = max(0, pos - self.PEPPER_SCALP_MIN_CORE)
            rich_now = bb - spot_fair
            cheap_now = spot_fair - ba

            # Clip small pops if we're already heavily long.
            if pos >= self.PEPPER_SCALP_MIN_CORE + 4 and rich_now >= self.PEPPER_SCALP_SELL_EDGE:
                bid_avail = max(0, depth.buy_orders.get(bb, 0))
                qty = min(self.PEPPER_SCALP_UNIT, scalp_excess, bid_avail, self.PEPPER_SCALP_MAX_INV)
                if qty > 0:
                    out.append(Order(product, bb, -qty))
                    pos -= qty

            # Rebuy small dips to restore the carry book.
            if pos < limit and cheap_now >= self.PEPPER_SCALP_BUY_EDGE:
                ask_avail = max(0, -depth.sell_orders.get(ba, 0))
                qty = min(self.PEPPER_SCALP_UNIT, scalp_shortfall, ask_avail)
                if qty > 0:
                    out.append(Order(product, ba, qty))
                    pos += qty

        buy_room = limit - pos
        sell_room = limit + pos
        under = max(0, target - pos)
        over = max(0, pos - target)

        best_inside_bid = bb + 1 if bb is not None else int(math.floor(spot_fair - 6))
        best_inside_ask = ba - 1 if ba is not None else int(math.ceil(spot_fair + 6))

        # A touch tighter on the bid than v3.1 so we get filled sooner without turning into pure churn.
        bid_quote = int(math.floor(min(carry_fair - 2.2, best_inside_bid)))
        ask_quote = int(math.ceil(max(spot_fair + 5.5, best_inside_ask)))
        if ask_quote <= bid_quote:
            ask_quote = bid_quote + 1

        bid_size = 0
        ask_size = 0
        if t < self.PEPPER_UNWIND_START:
            if under > 0:
                base = 16 if t < 8000 else (12 if t < 18000 else 10)
                bid_size = min(buy_room, min(self.PEPPER_MAX_PASSIVE, base + under // 2))
            elif pos < limit:
                bid_size = min(buy_room, 4)
            # Keep ask extremely light until we're materially over target.
            if pos > target + 18:
                ask_size = min(sell_room, min(6, 3 + over // 4))
        else:
            if pos > 0:
                ask_size = min(sell_room, min(self.PEPPER_MAX_PASSIVE, 10 + over // 2))
            elif pos < 0:
                bid_size = min(buy_room, 6)

        if bid_size > 0 and buy_room > 0:
            out.append(Order(product, bid_quote, bid_size))
        if ask_size > 0 and sell_room > 0:
            out.append(Order(product, ask_quote, -ask_size))

        if t >= self.PEPPER_FORCE_FLAT:
            if pos > 0 and bb is not None:
                bid_avail = max(0, depth.buy_orders.get(bb, 0))
                qty = min(pos, bid_avail)
                if qty > 0:
                    out.append(Order(product, bb, -qty))
            elif pos < 0 and ba is not None:
                ask_avail = max(0, -depth.sell_orders.get(ba, 0))
                qty = min(-pos, ask_avail)
                if qty > 0:
                    out.append(Order(product, ba, qty))

        return self.merge_same_price_orders(product, out)

    def pepper_target_position(self, t: float, limit: int) -> int:
        # Front-load size materially more than v3.1.
        if t < 1500:
            return int(round(limit * 0.95))
        if t < 6000:
            frac = (t - 1500.0) / 4500.0
            return int(round(limit * (0.95 + 0.05 * frac)))
        if t < self.PEPPER_UNWIND_START:
            return limit
        if t < 920000:
            frac = (t - self.PEPPER_UNWIND_START) / (920000.0 - self.PEPPER_UNWIND_START)
            return int(round(limit - frac * (limit - 30)))
        if t < self.PEPPER_FORCE_FLAT:
            frac = (t - 920000.0) / (self.PEPPER_FORCE_FLAT - 920000.0)
            return int(round(30 * (1.0 - frac)))
        return 0

    # ========================= Osmium =========================

    def trade_osmium(self, product: str, state: TradingState, mem: dict) -> List[Order]:
        depth = state.order_depths[product]
        pos = state.position.get(product, 0)
        limit = self.POSITION_LIMITS[product]
        out: List[Order] = []

        bb = self.best_bid(depth)
        ba = self.best_ask(depth)
        mid = self.mid_price(depth)
        if mid is None:
            return out

        prev_mu = float(mem.get("osmium_mu", self.OSMIUM_DEFAULT_FAIR))
        prev_var = float(mem.get("osmium_var", 16.0))
        mu = (1.0 - self.OSMIUM_MEAN_ALPHA) * prev_mu + self.OSMIUM_MEAN_ALPHA * mid
        dev = mid - prev_mu
        var = (1.0 - self.OSMIUM_VAR_ALPHA) * prev_var + self.OSMIUM_VAR_ALPHA * (dev * dev)
        sigma = max(1.8, min(9.0, math.sqrt(max(0.25, var))))

        fair = mu
        if bb is not None and ba is not None:
            bbv = max(0, depth.buy_orders.get(bb, 0))
            bav = max(0, -depth.sell_orders.get(ba, 0))
            tot = bbv + bav
            if tot > 0:
                fair += self.OSMIUM_IMBALANCE_WEIGHT * (bbv - bav) / tot

        fair -= self.OSMIUM_INV_SKEW * pos
        mem["osmium_mu"] = mu
        mem["osmium_var"] = var

        signal = (mid - fair) / sigma
        desired = 0
        if signal <= -self.OSMIUM_EXIT_Z:
            desired = min(self.OSMIUM_MAX_TARGET, int(round((-signal) * self.OSMIUM_TARGET_SCALE)))
        elif signal >= self.OSMIUM_EXIT_Z:
            desired = -min(self.OSMIUM_MAX_TARGET, int(round(signal * self.OSMIUM_TARGET_SCALE)))

        # Aggressive only for true dislocations. Crossing the spread casually has been a loser.
        take_band = self.OSMIUM_TAKE_Z * sigma
        if ba is not None and pos < desired and ba <= fair - take_band:
            ask_avail = max(0, -depth.sell_orders.get(ba, 0))
            qty = min(desired - pos, ask_avail, self.OSMIUM_MAX_CROSS)
            if qty > 0:
                out.append(Order(product, ba, qty))
                pos += qty
        if bb is not None and pos > desired and bb >= fair + take_band:
            bid_avail = max(0, depth.buy_orders.get(bb, 0))
            qty = min(pos - desired, bid_avail, self.OSMIUM_MAX_CROSS)
            if qty > 0:
                out.append(Order(product, bb, -qty))
                pos -= qty

        buy_room = limit - pos
        sell_room = limit + pos
        best_inside_bid = bb + 1 if bb is not None else int(math.floor(fair - sigma))
        best_inside_ask = ba - 1 if ba is not None else int(math.ceil(fair + sigma))

        # Quote closer than v3.3 to harvest more passive fills, but still avoid casual crossing.
        buy_offset = 0.30 * sigma - (0.10 * sigma if pos < -12 else 0.0)
        sell_offset = 0.30 * sigma - (0.10 * sigma if pos > 12 else 0.0)
        bid_quote = int(math.floor(min(fair - buy_offset, best_inside_bid)))
        ask_quote = int(math.ceil(max(fair + sell_offset, best_inside_ask)))
        if ask_quote <= bid_quote:
            ask_quote = bid_quote + 1

        bid_size = 0
        ask_size = 0

        if signal <= -self.OSMIUM_ENTRY_Z:
            core = max(9, min(self.OSMIUM_MAX_PASSIVE + 6, desired - pos + 3))
            bid_size = min(buy_room, core)
            ask_size = min(sell_room, 3 if pos > 16 else 1)
        elif signal >= self.OSMIUM_ENTRY_Z:
            core = max(9, min(self.OSMIUM_MAX_PASSIVE + 6, pos - desired + 3))
            ask_size = min(sell_room, core)
            bid_size = min(buy_room, 3 if pos < -16 else 1)
        else:
            # Neutral zone: always show both sides and participate more than v3.3.
            if pos > 24:
                ask_size = min(sell_room, min(self.OSMIUM_MAX_PASSIVE + 4, 10 + pos // 6))
                bid_size = min(buy_room, 3)
            elif pos < -24:
                bid_size = min(buy_room, min(self.OSMIUM_MAX_PASSIVE + 4, 10 + (-pos) // 6))
                ask_size = min(sell_room, 3)
            elif pos > 10:
                ask_size = min(sell_room, 8 + pos // 8)
                bid_size = min(buy_room, 4)
            elif pos < -10:
                bid_size = min(buy_room, 8 + (-pos) // 8)
                ask_size = min(sell_room, 4)
            else:
                bid_size = min(buy_room, 6)
                ask_size = min(sell_room, 6)

        if bid_size > 0:
            out.append(Order(product, bid_quote, bid_size))
        if ask_size > 0:
            out.append(Order(product, ask_quote, -ask_size))

        # Hard inventory clamps.
        if pos > 72 and bb is not None:
            bid_avail = max(0, depth.buy_orders.get(bb, 0))
            qty = min(pos - 72, bid_avail)
            if qty > 0:
                out.append(Order(product, bb, -qty))
        if pos < -72 and ba is not None:
            ask_avail = max(0, -depth.sell_orders.get(ba, 0))
            qty = min(-72 - pos, ask_avail)
            if qty > 0:
                out.append(Order(product, ba, qty))

        return self.merge_same_price_orders(product, out)

    # ========================= Helpers =========================

    def _maybe_reset_for_new_day(self, state: TradingState, mem: dict) -> None:
        t = int(getattr(state, "timestamp", 0))
        last_t = mem.get("last_timestamp")
        if last_t is not None and t < int(last_t):
            mem["pepper_intercept"] = None
            mem["osmium_mu"] = self.OSMIUM_DEFAULT_FAIR
            mem["osmium_var"] = 16.0

    @staticmethod
    def best_bid(depth) -> Optional[int]:
        return max(depth.buy_orders.keys()) if depth.buy_orders else None

    @staticmethod
    def best_ask(depth) -> Optional[int]:
        return min(depth.sell_orders.keys()) if depth.sell_orders else None

    def mid_price(self, depth) -> Optional[float]:
        bb = self.best_bid(depth)
        ba = self.best_ask(depth)
        if bb is not None and ba is not None:
            return (bb + ba) / 2.0
        if bb is not None:
            return float(bb)
        if ba is not None:
            return float(ba)
        return None

    @staticmethod
    def _load_state(raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    @staticmethod
    def merge_same_price_orders(product: str, orders: List[Order]) -> List[Order]:
        merged: Dict[int, int] = {}
        for order in orders:
            merged[order.price] = merged.get(order.price, 0) + order.quantity
        return [Order(product, price, qty) for price, qty in merged.items() if qty != 0]
