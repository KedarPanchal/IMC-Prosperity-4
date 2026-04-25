"""Apply centroid params to r3.py and run a final sanity backtest."""
import re
from simulator import run_with_params

# ── Paste the output from centroid.py here ────────────────────────────────────
RECOMMENDED: dict = {"HYDROGEL_EMA_ALPHA": 0.15, "HYDROGEL_TAKE_EDGE": 10, "MAX_TAKE_PER_TICK": 5, "SKEW_HEAVY": 0.3}

R3_PATH = "r3.py"   # path to your algo file

# ─────────────────────────────────────────────────────────────────────────────

def patch_r3(params: dict, src_path: str = R3_PATH) -> None:
    with open(src_path) as f:
        src = f.read()
    for k, v in params.items():
        pattern = re.compile(
            rf"^({re.escape(k)}\s*=\s*)([^\s#]+)(.*)$", re.MULTILINE)
        src = pattern.sub(rf"\g<1>{v}\g<3>", src, count=1)
    with open(src_path, "w") as f:
        f.write(src)
    print(f"Patched {src_path}:")
    for k, v in params.items():
        print(f"  {k:25s} = {v}")

def verify(params: dict) -> None:
    print("\nFinal 3-day backtest with centroid params:")
    res = run_with_params(params, days=(0, 1, 2))
    print(f"  3-day PnL : {res['pnl']:+.2f}")
    for day, pnl in sorted(res["pnl_per_day"].items()):
        print(f"  Day {day}     : {pnl:+.2f}")
    print(f"  Total fills: {res['fills']}")
    if res.get("error"):
        print(f"  ERROR: {res['error']}")

if __name__ == "__main__":
    if not RECOMMENDED:
        print("Set RECOMMENDED dict first (copy-paste from centroid.py output).")
    else:
        verify(RECOMMENDED)
        ans = input("\nPatch r3.py with these params? [y/N] ").strip().lower()
        if ans == "y":
            patch_r3(RECOMMENDED)
        else:
            print("r3.py unchanged.")
