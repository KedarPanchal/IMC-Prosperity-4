"""
CLI: enumerate EV grid for both products, export CSV + heatmaps + reports.

Casual: Run this to get ranked strategies and plots.
Formal: Implements plan todos encode-mechanism, enumerate-candidates-ev,
scan-knife-edges, compare-buy-sell, and documents confirm-short-rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from intarian_welcome.clearing_simulator import ClearingSimulator, OrderSide, ProductParams
from intarian_welcome.ev_enumeration import (
    CandidateRow,
    build_quantity_grid,
    compare_best_long_short,
    default_price_range,
    evaluate_grid,
    evaluate_pairs,
    knife_edge_near_best,
    merge_dedupe_rows,
    random_supplement_candidates,
    rows_to_numpy_for_heatmap,
    save_csv,
    save_heatmap_png,
    top_k,
)
from intarian_welcome.frozen_books import (
    DRYLAND_FLAX_ASKS,
    DRYLAND_FLAX_BIDS,
    EMBER_MUSHROOM_ASKS,
    EMBER_MUSHROOM_BIDS,
)


def _params_flax() -> ProductParams:
    """Buyback 30; no fees on flax."""

    return ProductParams(
        name="DRYLAND_FLAX",
        buyback_anchor=30.0,
        fee_long=0.0,
        fee_short=0.0,
    )


def _params_mushroom() -> ProductParams:
    """Buyback 20; 0.10 fee on buyback leg (long and short cover)."""

    return ProductParams(
        name="EMBER_MUSHROOM",
        buyback_anchor=20.0,
        fee_long=0.10,
        fee_short=0.10,
    )


def _run_one_product(
    bids: dict[int, int],
    asks: dict[int, int],
    params: ProductParams,
    out_dir: Path,
    price_pad: int,
    qty_cap: int,
    linear_step: int,
    log_samples: int,
    dense_through: int,
    random_samples: int,
    top_n: int,
    heatmap: bool,
) -> dict:
    """Run grid + optional random supplement; write artifacts."""

    lo, hi = default_price_range(bids, asks)
    price_lo = lo - price_pad
    price_hi = hi + price_pad
    quantities = build_quantity_grid(
        qty_cap,
        linear_step,
        log_samples,
        dense_through=dense_through,
    )

    sim = ClearingSimulator(bids, asks, params)
    rows = evaluate_grid(sim, params, price_lo, price_hi, quantities)

    if random_samples > 0:
        rng = __import__("numpy").random.default_rng(42)
        pairs = random_supplement_candidates(rng, random_samples, price_lo, price_hi, qty_cap)
        rows = merge_dedupe_rows(list(rows) + evaluate_pairs(sim, params, pairs))

    save_csv(rows, out_dir / f"{params.name}_all_candidates.csv")
    best = top_k(rows, top_n)

    cmp_ls = compare_best_long_short(rows)

    def _row_dict(r: CandidateRow | None) -> dict | None:
        if r is None:
            return None
        return {
            "side": r.side,
            "limit_price": r.limit_price,
            "quantity": r.quantity,
            "profit": r.profit,
            "clearing_price": r.clearing_price,
            "user_filled_qty": r.user_filled_qty,
        }

    report = {
        "product": params.name,
        "price_range": [price_lo, price_hi],
        "num_quantities": len(quantities),
        "num_rows": len(rows),
        "best_long": _row_dict(cmp_ls["best_long_row"]),
        "best_short": _row_dict(cmp_ls["best_short_row"]),
        "best_short_positive_fill": _row_dict(cmp_ls["best_short_row_positive_fill"]),
        "long_profit_ge_short": cmp_ls["long_beats_short_profit"],
    }

    knife_list = []
    for r in best[: min(15, len(best))]:
        knife_list.append(
            {
                "limit_price": r.limit_price,
                "side": r.side,
                "quantity": r.quantity,
                "profit": r.profit,
                **knife_edge_near_best(sim, r, delta_qty=1),
            }
        )
    report["knife_edges_top_candidates"] = knife_list

    with (out_dir / f"{params.name}_summary.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    if heatmap:
        import numpy as np

        for side, label in ((OrderSide.BID, "bid_long"), (OrderSide.ASK, "ask_short")):
            prices, qtys, grid = rows_to_numpy_for_heatmap(rows, side)
            if grid.size == 0:
                continue
            # Very wide q-grids make huge PNGs; subsample columns for readability.
            max_cols = 520
            if grid.shape[1] > max_cols:
                step = int(np.ceil(grid.shape[1] / max_cols))
                qtys = qtys[::step]
                grid = grid[:, ::step]
            save_heatmap_png(
                prices,
                qtys,
                grid,
                title=f"{params.name} profit ({label})",
                path=out_dir / f"{params.name}_heatmap_{label}.png",
            )

    return report


def main(argv: list[str] | None = None) -> int:
    """Parse CLI and write output directory."""

    p = argparse.ArgumentParser(description="Intarian Welcome EV grid search")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("output") / "intarian_welcome",
        help="Output directory for CSV/JSON/PNGs",
    )
    p.add_argument("--price-pad", type=int, default=0, help="Extend price range beyond book min/max")
    p.add_argument("--qty-cap", type=int, default=120_000, help="Max quantity in grid")
    p.add_argument("--linear-step", type=int, default=500, help="Linear grid step for quantity")
    p.add_argument("--log-samples", type=int, default=45, help="Number of log-spaced quantity samples")
    p.add_argument("--random-samples", type=int, default=2500, help="Extra random (side,price,qty) draws")
    p.add_argument(
        "--dense-through",
        type=int,
        default=25_000,
        help="Include every integer quantity 1..dense_through (capped by --qty-cap) for knife-edges",
    )
    p.add_argument("--top", type=int, default=50, help="How many top rows to print")
    p.add_argument("--no-heatmap", action="store_true", help="Skip PNG heatmaps")
    args = p.parse_args(argv)

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    reports = []
    reports.append(
        _run_one_product(
            DRYLAND_FLAX_BIDS,
            DRYLAND_FLAX_ASKS,
            _params_flax(),
            out_dir,
            price_pad=args.price_pad,
            qty_cap=args.qty_cap,
            linear_step=args.linear_step,
            log_samples=args.log_samples,
            dense_through=args.dense_through,
            random_samples=args.random_samples,
            top_n=args.top,
            heatmap=not args.no_heatmap,
        )
    )
    reports.append(
        _run_one_product(
            EMBER_MUSHROOM_BIDS,
            EMBER_MUSHROOM_ASKS,
            _params_mushroom(),
            out_dir,
            price_pad=args.price_pad,
            qty_cap=args.qty_cap,
            linear_step=args.linear_step,
            log_samples=args.log_samples,
            dense_through=args.dense_through,
            random_samples=args.random_samples,
            top_n=args.top,
            heatmap=not args.no_heatmap,
        )
    )

    print(json.dumps(reports, indent=2))
    for rep in reports:
        print("\n===", rep["product"], "top long / short ===")
        print("best_long:", rep.get("best_long"))
        print("best_short:", rep.get("best_short"))
        print("best_short_positive_fill:", rep.get("best_short_positive_fill"))
        print("long >= short profit:", rep.get("long_profit_ge_short"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
