"""4-D grid search over the most sensitive parameters.

5 × 5 × 3 × 3 = 225 evaluations.  Saves /tmp/grid_results.json.
"""
import itertools, json, time
from simulator import run_with_params

BASELINE = {
    "VEV_IV_PRIOR":       0.27,
    "FLOW_GATE_TICKS":    2,
    "FLOW_FAST_N":        3,
    "FLOW_SLOW_N":        15,
    "FLOW_THRESH":        0.5,
    "HYDROGEL_EMA_ALPHA": 0.05,
    "HYDROGEL_TAKE_EDGE": 6,
    "MAX_TAKE_PER_TICK":  8,
    "MAX_PASSIVE_QTY":    12,
    "SKEW_HEAVY":         0.50,
    "SKEW_LIGHT":         0.20,
}

GRID = {
    "HYDROGEL_EMA_ALPHA": [0.05, 0.10, 0.15, 0.20, 0.25],
    "HYDROGEL_TAKE_EDGE": [6, 8, 10, 12, 14],
    "MAX_TAKE_PER_TICK":  [3, 5, 8],
    "SKEW_HEAVY":         [0.30, 0.40, 0.50],
}

def main():
    keys   = list(GRID.keys())
    combos = list(itertools.product(*[GRID[k] for k in keys]))
    print(f"Running {len(combos)} grid points …")

    results = []
    t0 = time.time()
    for i, combo in enumerate(combos):
        params = dict(BASELINE)
        for k, v in zip(keys, combo):
            params[k] = v

        d0  = run_with_params(params, days=(0,))["pnl"]
        d1  = run_with_params(params, days=(1,))["pnl"]
        d2  = run_with_params(params, days=(2,))["pnl"]

        results.append({
            "params":  dict(zip(keys, combo)),
            "pnl_d0":  d0,
            "pnl_d1":  d1,
            "pnl_d2":  d2,
            "pnl_all": run_with_params(params, days=(0, 1, 2))["pnl"],
            "mean":    (d0 + d1 + d2) / 3,
            "min":     min(d0, d1, d2),
        })
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            eta     = elapsed / (i + 1) * (len(combos) - i - 1)
            print(f"  {i+1}/{len(combos)}  elapsed={elapsed:.0f}s  eta={eta:.0f}s")

    print(f"\nDone in {time.time()-t0:.0f}s")

    with open("/tmp/grid_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved → /tmp/grid_results.json\n")

    # ── Top-20 by mean P&L ────────────────────────────────────────────────────
    by_mean = sorted(results, key=lambda r: -r["mean"])
    print("=== TOP 20 by MEAN P&L ===")
    for r in by_mean[:20]:
        p = r["params"]
        print(f"  α={p['HYDROGEL_EMA_ALPHA']:.2f} "
              f"edge={p['HYDROGEL_TAKE_EDGE']:>2} "
              f"take={p['MAX_TAKE_PER_TICK']:>2} "
              f"skew={p['SKEW_HEAVY']:.2f} "
              f"| d0={r['pnl_d0']:+8.0f} d1={r['pnl_d1']:+8.0f} "
              f"d2={r['pnl_d2']:+8.0f} mean={r['mean']:+8.0f} "
              f"min={r['min']:+8.0f}")

    # ── Top-20 by worst-day P&L (robustness) ─────────────────────────────────
    by_min = sorted(results, key=lambda r: -r["min"])
    print("\n=== TOP 20 by MIN P&L (worst-day robustness) ===")
    for r in by_min[:20]:
        p = r["params"]
        print(f"  α={p['HYDROGEL_EMA_ALPHA']:.2f} "
              f"edge={p['HYDROGEL_TAKE_EDGE']:>2} "
              f"take={p['MAX_TAKE_PER_TICK']:>2} "
              f"skew={p['SKEW_HEAVY']:.2f} "
              f"| d0={r['pnl_d0']:+8.0f} d1={r['pnl_d1']:+8.0f} "
              f"d2={r['pnl_d2']:+8.0f} mean={r['mean']:+8.0f} "
              f"min={r['min']:+8.0f}")

if __name__ == "__main__":
    main()
