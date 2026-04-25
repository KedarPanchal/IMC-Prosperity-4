"""
Backtest simulator for r3.py against historical days 0, 1, 2.

Fill model:
  - Aggressive (price-crossing): fills at touch up to displayed depth.
  - Passive: fills if actual market trades at this tick occurred at a
    compatible price (incoming flow consumed our level).

Mark-to-market at end of each day's last mid; sum across days.
"""
import csv, json, sys, types, math, importlib
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import os

# ── Stub the IMC datamodel ────────────────────────────────────────────────────

class Order:
    __slots__ = ("symbol", "price", "quantity")
    def __init__(self, s, p, q):
        self.symbol   = s
        self.price    = int(p)
        self.quantity = int(q)
    def __repr__(self):
        return f"Order({self.symbol},{self.price:+d},{self.quantity:+d})"

class OrderDepth:
    __slots__ = ("buy_orders", "sell_orders")
    def __init__(self):
        self.buy_orders:  Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}

class TradingState:
    def __init__(self):
        self.timestamp    = 0
        self.order_depths: Dict[str, OrderDepth] = {}
        self.position:     Dict[str, int]         = {}
        self.traderData   = ""

_dm = types.ModuleType("datamodel")
_dm.Order        = Order
_dm.OrderDepth   = OrderDepth
_dm.TradingState = TradingState
sys.modules["datamodel"] = _dm

# ── Data directory: resolved relative to this file ───────────────────────────
# CSVs must be named  prices_round_3_day_{N}.csv  /  trades_round_3_day_{N}.csv
# By default we look next to this script; override DATA_DIR env var if needed.
DATA_DIR = os.environ.get(
    "ROUND3_DATA",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "round3_data"),
)

PRODUCTS = (
    "HYDROGEL_PACK", "VELVETFRUIT_EXTRACT",
    "VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100",
    "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500",
    "VEV_6000", "VEV_6500",
)

# ── CSV loading ───────────────────────────────────────────────────────────────

def _build_book(row) -> OrderDepth:
    od = OrderDepth()
    for px_idx, vol_idx in [(3, 4), (5, 6), (7, 8)]:
        if row[px_idx] and row[vol_idx]:
            try:
                od.buy_orders[int(row[px_idx])] = int(row[vol_idx])
            except ValueError:
                pass
    for px_idx, vol_idx in [(9, 10), (11, 12), (13, 14)]:
        if row[px_idx] and row[vol_idx]:
            try:
                od.sell_orders[int(row[px_idx])] = -int(row[vol_idx])
            except ValueError:
                pass
    return od


def load_day(day: int, sample_step: int = 100):
    """Return (snapshots, market_trades).

    snapshots     : [(timestamp*10, {product: OrderDepth}), ...]
    market_trades : {timestamp*10: [(symbol, price, qty), ...]}
    """
    snaps: Dict[int, Dict[str, OrderDepth]] = {}
    path = os.path.join(DATA_DIR, f"prices_round_3_day_{day}.csv")
    with open(path) as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            if len(row) < 15:
                continue
            try:
                ts = int(row[1])
            except ValueError:
                continue
            if ts % sample_step != 0:
                continue
            prod = row[2]
            if prod not in PRODUCTS:
                continue
            snaps.setdefault(ts, {})[prod] = _build_book(row)

    trades: Dict[int, List[Tuple[str, float, int]]] = defaultdict(list)
    tpath  = os.path.join(DATA_DIR, f"trades_round_3_day_{day}.csv")
    with open(tpath) as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            if len(row) < 7:
                continue
            try:
                ts  = int(row[0])
                sym = row[3]
                px  = float(row[5])
                qty = int(row[6])
            except ValueError:
                continue
            ts_snap = (ts // sample_step) * sample_step
            trades[ts_snap * 10].append((sym, px, qty))

    snaps_list = [(ts * 10, snaps[ts]) for ts in sorted(snaps)]
    return snaps_list, trades

# ── Fill model ────────────────────────────────────────────────────────────────

def _aggressive_fills(order: Order, od: OrderDepth) -> List[Tuple[int, int]]:
    fills     = []
    remaining = order.quantity
    if remaining > 0:
        for px in sorted(od.sell_orders):
            if px > order.price or remaining <= 0:
                break
            avail = -od.sell_orders[px]
            qty   = min(remaining, avail)
            if qty > 0:
                fills.append((px, qty))
                remaining -= qty
    elif remaining < 0:
        for px in sorted(od.buy_orders, reverse=True):
            if px < order.price or remaining >= 0:
                break
            avail = od.buy_orders[px]
            qty   = min(-remaining, avail)
            if qty > 0:
                fills.append((px, -qty))
                remaining += qty
    return fills


def _passive_fills_from_trades(orders: List[Order],
                                od_now: OrderDepth,
                                trades_at_ts: List[Tuple[str, float, int]],
                                product: str) -> List[Tuple[int, int]]:
    fills: List[Tuple[int, int]] = []
    if not od_now.buy_orders or not od_now.sell_orders:
        return fills
    now_bb = max(od_now.buy_orders)
    now_ba = min(od_now.sell_orders)

    bid_compat_volume = sum(int(q) for s, p, q in trades_at_ts
                            if s == product and p <= now_bb)
    ask_compat_volume = sum(int(q) for s, p, q in trades_at_ts
                            if s == product and p >= now_ba)
    bid_remaining = bid_compat_volume
    ask_remaining = ask_compat_volume

    sorted_orders = sorted(orders,
                           key=lambda o: -o.price if o.quantity > 0 else o.price)
    for o in sorted_orders:
        if o.quantity > 0 and o.price < now_ba and bid_remaining > 0:
            qty = min(o.quantity, bid_remaining)
            fills.append((o.price, qty))
            bid_remaining -= qty
        elif o.quantity < 0 and o.price > now_bb and ask_remaining > 0:
            qty = min(-o.quantity, ask_remaining)
            fills.append((o.price, -qty))
            ask_remaining -= qty
    return fills

# ── Run the trader ────────────────────────────────────────────────────────────

def run_backtest(trader_module_name: str = "r3",
                 days: Tuple[int, ...] = (0, 1, 2),
                 use_passive_fills: bool = True,
                 verbose: bool = False,
                 param_overrides: Optional[Dict] = None) -> Dict:
    if trader_module_name in sys.modules:
        del sys.modules[trader_module_name]
    mod = importlib.import_module(trader_module_name)
    if param_overrides:
        for k, v in param_overrides.items():
            if hasattr(mod, k):
                setattr(mod, k, v)
    Trader = mod.Trader

    trader        = Trader()
    position:     Dict[str, int]   = defaultdict(int)
    cash          = 0.0
    td            = ""
    pnl_per_day:  Dict[int, float] = {}
    fill_count    = 0
    last_mids:    Dict[str, float] = {}

    for day in days:
        snaps, market_trades = load_day(day)
        if td:
            try:
                td_obj = json.loads(td)
                td_obj["day"]     = day
                td_obj["prev_ts"] = -1
                td = json.dumps(td_obj)
            except Exception:
                pass
        else:
            td = json.dumps({"day": day, "prev_ts": -1})

        for i, (ts, books) in enumerate(snaps):
            state             = TradingState()
            state.timestamp   = ts
            state.order_depths = books
            state.position    = dict(position)
            state.traderData  = td

            try:
                result, _, td = trader.run(state)
            except Exception as e:
                if verbose:
                    print(f"  ERROR at day={day} ts={ts}: {e}")
                return {"pnl": -1e9, "error": str(e), "fills": fill_count}

            trades_at_ts = market_trades.get(ts, [])

            for prod, orders in result.items():
                od_now = books.get(prod)
                if not od_now:
                    continue
                aggressive_filled = set()
                for idx, o in enumerate(orders):
                    fills = _aggressive_fills(o, od_now)
                    if fills:
                        aggressive_filled.add(idx)
                    for fpx, fqty in fills:
                        position[prod] += fqty
                        cash           -= fpx * fqty
                        fill_count     += 1
                if use_passive_fills:
                    passive = [o for idx, o in enumerate(orders)
                               if idx not in aggressive_filled]
                    for fpx, fqty in _passive_fills_from_trades(
                            passive, od_now, trades_at_ts, prod):
                        position[prod] += fqty
                        cash           -= fpx * fqty
                        fill_count     += 1

            for prod, od in books.items():
                if od.buy_orders and od.sell_orders:
                    last_mids[prod] = (max(od.buy_orders) +
                                       min(od.sell_orders)) / 2

        mtm = sum(position[p] * last_mids.get(p, 0) for p in position)
        pnl_per_day[day] = cash + mtm

    final_pnl = pnl_per_day[days[-1]]
    return {
        "pnl":           final_pnl,
        "pnl_per_day":   pnl_per_day,
        "final_position": dict(position),
        "fills":         fill_count,
        "error":         None,
    }

# ── Param injection ───────────────────────────────────────────────────────────

PARAM_NAMES = (
    "VEV_IV_PRIOR", "FLOW_GATE_TICKS", "FLOW_FAST_N", "FLOW_SLOW_N",
    "FLOW_THRESH", "HYDROGEL_EMA_ALPHA", "HYDROGEL_TAKE_EDGE",
    "MAX_TAKE_PER_TICK", "MAX_PASSIVE_QTY", "SKEW_HEAVY", "SKEW_LIGHT",
)

def run_with_params(params: Dict[str, float],
                    days:   Tuple[int, ...] = (0, 1, 2),
                    use_passive_fills: bool = True) -> Dict:
    return run_backtest("r3", days, use_passive_fills, param_overrides=params)
