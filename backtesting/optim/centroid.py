"""Centroid-of-plateau analyzer — DBSCAN clustering + multimodality fallback.

Pipeline
--------
1.  Load /tmp/grid_results.json  (produced by grid.py).
2.  Plateau = top 20% by mean P&L.
3.  Normalize each param to [0, 1].
4.  DBSCAN with adaptive eps (= 1.5× mean normalized grid step).
5.  Pick the LARGEST cluster.
6.  Centroid of that cluster; snap each param to nearest grid value.
7.  Verify centroid P&L ≥ plateau threshold.
    • If it's a "hole" (below threshold) → fall back to densest-ball:
      the cluster point whose eps-neighbourhood has the highest mean P&L.
8.  Local gradient: perturb centroid ±1 grid step per param.
9.  Print copy-paste RECOMMENDED dict for apply_centroid.py.
"""
import json, math
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

try:
    from sklearn.cluster import DBSCAN
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from simulator import run_with_params

# ── Constants ─────────────────────────────────────────────────────────────────

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

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize(value: float, grid_values: List[float]) -> float:
    lo, hi = min(grid_values), max(grid_values)
    return 0.5 if hi == lo else (value - lo) / (hi - lo)

def denormalize_to_grid(norm_value: float, grid_values: List[float]) -> float:
    lo, hi = min(grid_values), max(grid_values)
    raw = lo + norm_value * (hi - lo)
    return min(grid_values, key=lambda v: abs(v - raw))

def to_norm_vec(params: Dict, keys: List[str]) -> List[float]:
    return [normalize(params[k], GRID[k]) for k in keys]

def euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def adaptive_eps(keys: List[str]) -> float:
    """1.5× mean normalized grid step — bridges adjacent grid points."""
    steps = [1.0 / (len(GRID[k]) - 1) for k in keys if len(GRID[k]) > 1]
    return (sum(steps) / len(steps)) * 1.5

# ── Pure-Python DBSCAN fallback ───────────────────────────────────────────────

def _pure_dbscan(points: List[List[float]], eps: float,
                 min_samples: int) -> List[int]:
    n       = len(points)
    labels  = [-1] * n
    visited = [False] * n
    cid     = 0

    def nbrs(i):
        return [j for j in range(n) if euclidean(points[i], points[j]) <= eps]

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        nb = nbrs(i)
        if len(nb) < min_samples:
            continue
        labels[i] = cid
        seed = list(nb)
        while seed:
            q = seed.pop()
            if not visited[q]:
                visited[q] = True
                qnb = nbrs(q)
                if len(qnb) >= min_samples:
                    seed.extend(qnb)
            if labels[q] == -1:
                labels[q] = cid
        cid += 1
    return labels

def run_dbscan(vecs: List[List[float]], eps: float,
               min_samples: int = 2) -> List[int]:
    if HAS_SKLEARN:
        arr = np.array(vecs)
        return DBSCAN(eps=eps, min_samples=min_samples).fit_predict(arr).tolist()
    return _pure_dbscan(vecs, eps, min_samples)

# ── Densest-ball fallback ─────────────────────────────────────────────────────

def densest_ball_center(cluster: List[Dict], keys: List[str],
                        eps: float) -> Dict:
    """Return the cluster point whose eps-neighbourhood has the highest
    mean P&L — i.e. the actual density peak, not the geometric centre."""
    vecs = [to_norm_vec(r["params"], keys) for r in cluster]
    pnls = [r["mean"] for r in cluster]
    best_idx, best_score = 0, -1e18
    for i, vi in enumerate(vecs):
        nb_pnls = [pnls[j] for j, vj in enumerate(vecs)
                   if euclidean(vi, vj) <= eps]
        score = sum(nb_pnls) / len(nb_pnls)
        if score > best_score:
            best_score, best_idx = score, i
    return cluster[best_idx]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    with open("/tmp/grid_results.json") as f:
        results = json.load(f)

    keys          = list(GRID.keys())
    sorted_r      = sorted(results, key=lambda r: -r["mean"])

    # 1. Plateau
    plateau_size  = max(5, len(sorted_r) // 5)
    plateau       = sorted_r[:plateau_size]
    threshold     = plateau[-1]["mean"]
    print(f"Plateau = top {plateau_size}/{len(results)}  "
          f"P&L range [{threshold:.0f}, {plateau[0]['mean']:.0f}]\n")

    # 2–3. Normalize + DBSCAN
    vecs        = [to_norm_vec(r["params"], keys) for r in plateau]
    eps         = adaptive_eps(keys)
    min_samples = max(2, plateau_size // 10)
    labels      = run_dbscan(vecs, eps=eps, min_samples=min_samples)

    clusters: Dict[int, List] = defaultdict(list)
    for r, lbl in zip(plateau, labels):
        clusters[lbl].append(r)

    n_clusters  = sum(1 for k in clusters if k != -1)
    noise_count = len(clusters.get(-1, []))
    print(f"DBSCAN  eps={eps:.3f}  min_samples={min_samples}  "
          f"→  {n_clusters} cluster(s)  ({noise_count} noise pts)")

    if n_clusters == 0:
        print("  All noise → using simple plateau centroid.")
        main_cluster = plateau
    else:
        best_cid     = max((k for k in clusters if k != -1),
                           key=lambda k: len(clusters[k]))
        main_cluster = clusters[best_cid]
        if n_clusters > 1:
            print(f"  ⚠  MULTIMODAL  ({n_clusters} clusters) — using largest "
                  f"(#{best_cid}, {len(main_cluster)} pts)")
            for cid, pts in sorted(clusters.items(), key=lambda x: -len(x[1])):
                if cid == -1:
                    continue
                ms = [r["mean"] for r in pts]
                print(f"     Cluster #{cid}: {len(pts)} pts  "
                      f"mean={sum(ms)/len(ms):.0f}  "
                      f"max={max(ms):.0f}  min={min(ms):.0f}")
        else:
            print(f"  Single cluster  ({len(main_cluster)} pts)")

    # 4. Centroid
    norm_c = {}
    raw_c  = {}
    for k in keys:
        nv       = [normalize(r["params"][k], GRID[k]) for r in main_cluster]
        norm_c[k] = sum(nv) / len(nv)
        raw_c[k]  = sum(r["params"][k] for r in main_cluster) / len(main_cluster)

    centroid_params = {k: denormalize_to_grid(norm_c[k], GRID[k]) for k in keys}

    print("\n=== CENTROID ===")
    for k in keys:
        print(f"  {k:25s}  norm={norm_c[k]:.3f}  "
              f"raw_mean={raw_c[k]:.4f}  snapped={centroid_params[k]}")

    # 5. Verify
    centroid_match = next(
        (r for r in results
         if all(r["params"][k] == centroid_params[k] for k in keys)), None)
    use_centroid = True

    if centroid_match:
        rank = sorted_r.index(centroid_match) + 1
        print(f"\nCentroid → grid rank #{rank}/{len(results)}  "
              f"mean={centroid_match['mean']:.0f}  "
              f"d0={centroid_match['pnl_d0']:+.0f}  "
              f"d1={centroid_match['pnl_d1']:+.0f}  "
              f"d2={centroid_match['pnl_d2']:+.0f}")
        if centroid_match["mean"] >= threshold:
            print(f"  [OK]   Centroid in plateau (≥ {threshold:.0f})")
        else:
            print(f"  [WARN] Centroid below threshold ({threshold:.0f}) "
                  "→ hole in plateau; falling back to densest-ball.")
            use_centroid = False
    else:
        print("\n  [INFO] Centroid not in grid; running densest-ball fallback.")
        use_centroid = False

    # 5b. Densest-ball fallback
    if not use_centroid:
        best      = densest_ball_center(main_cluster, keys, eps)
        centroid_params = dict(best["params"])
        centroid_match  = best
        rank = sorted_r.index(best) + 1
        print(f"  Densest-ball: rank #{rank}  mean={best['mean']:.0f}")
        for k in keys:
            print(f"    {k:25s} = {centroid_params[k]}")

    # 6. Local gradient
    base_pnl = centroid_match["mean"] if centroid_match else None
    full_base = {**BASELINE, **centroid_params}

    print("\n=== LOCAL GRADIENT ===")
    if base_pnl is None:
        print("  (centroid P&L unknown)")
    else:
        for k in keys:
            idx = GRID[k].index(centroid_params[k])
            for delta in (-1, +1):
                ni = idx + delta
                if not (0 <= ni < len(GRID[k])):
                    continue
                nbr_params = {**full_base, k: GRID[k][ni]}
                match = next(
                    (r for r in results
                     if all(r["params"][k2] == nbr_params[k2] for k2 in keys)),
                    None)
                npnl = match["mean"] if match else \
                       run_with_params(nbr_params, days=(0, 1, 2))["pnl"]
                sign = "▼" if npnl < base_pnl else "▲"
                pct  = 100 * (npnl - base_pnl) / max(abs(base_pnl), 1)
                print(f"  {k:25s}  {centroid_params[k]} → {GRID[k][ni]:<6}  "
                      f"mean={npnl:+.0f}  {sign} {pct:+.1f}%")

    # 7. TOP-1 comparison
    top1 = sorted_r[0]
    print(f"\n=== TOP-1 (max mean) ===  {top1['params']}")
    print(f"  d0={top1['pnl_d0']:+.0f}  d1={top1['pnl_d1']:+.0f}  "
          f"d2={top1['pnl_d2']:+.0f}  mean={top1['mean']:+.0f}")
    if centroid_match:
        print(f"  Centroid trades {top1['mean'] - centroid_match['mean']:.0f} "
              "mean P&L for robustness.")

    # 8. Recommendation
    print("\n=== RECOMMENDATION ===")
    for k, v in centroid_params.items():
        bv     = BASELINE[k]
        change = "" if v == bv else f"  (was {bv})"
        print(f"  {k:25s} = {v}{change}")

    items = ", ".join(f'"{k}": {v}' for k, v in centroid_params.items())
    print(f"\nCopy-paste into apply_centroid.py:\n"
          f"  RECOMMENDED = {{{items}}}")

if __name__ == "__main__":
    main()
