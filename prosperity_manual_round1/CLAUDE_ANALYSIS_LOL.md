Yes, this solution makes sense and is well-optimized. Here's why:
DRYLAND_FLAX: Bid 30, qty 9,999

The key insight: Without your order, clearing = 28 (volume 40k). By bidding at 30 with qty < 10k, you push cumulative bids ≥ 29 to 44,999 — enough to tie volume at 40k for both prices 28 and 29. The tie-break rule picks 29 as clearing price.
But if you bid ≥ 10k, bids at price 30 alone reach 40k, tying volume all the way up to price 30, and clearing jumps to 30 — killing your margin.
So 9,999 is the maximum quantity that keeps clearing at 29. You buy 9,999 at 29, sell at buyback 30 → profit = 9,999.
EMBER_MUSHROOM: Bid 17, qty 19,999
Same logic. Without your order, clearing = 16 (volume 81k, tied at 15 and 16, tie-break → 16). By bidding at 17 with qty 19,999, cumulative bids ≥ 17 become 90,999, while asks ≤ 17 = 91k — so volume at 17 is only 90,999, still less than 91k at price 16. Clearing stays at 16.
If you bid 20k instead, bids ≥ 17 = 91k = asks ≤ 17, tying volume at 91k for prices 16 and 17, pushing clearing to 17 and costing you ~20k in profit.
Your fill: after 66k of higher-priority bids (≥18) and 5k existing at 17, you get all 19,999 units. Buy at 16, sell at buyback 19.90 (after fee) → profit = 3.90 × 19,999 ≈ 77,996.
Total: ~87,995
The "quantity = threshold − 1" pattern is the right approach for both products — it maximizes fill while staying just below the tipping point that would raise the clearing price.

---

# Second-pass analysis and confirmation (Cursor)

Independent re-derivation against the frozen books in `intarian_welcome/frozen_books.py` and the rules in `.cursor/rules/round1.md`. Conclusion up front: **the recommended orders are optimal**; being last in line is already baked in; both picks sit on one-unit knife edges; the short-side numbers in the grid output are likely not actionable under the posted rules.

## Auction mechanics used

From `round1.md` and `clearing_simulator.py`:

1. Uniform clearing price `P*` maximizes total traded volume `V(P) = min(D(P), S(P))`.
2. Tie-break: among all `P` achieving `max V`, pick the **highest**.
3. Allocation: **price priority**, then **time priority** at the same price.
4. You submit last, so at your own price level all resting orders fill before you.

## Dryland Flax — confirm `bid 30 × 9999 → +9999`

Resting book (from `frozen_books.py`):

- Bids: `30→30k, 29→5k, 28→12k, 27→28k`
- Asks: `28→40k, 31→20k, 32→20k, 33→30k`
- Buyback anchor: `30` (no fee)

Volume curve without the user:

| P | D(P) | S(P) | V(P) |
|---|------|------|------|
| 28 | 47,000 | 40,000 | 40,000 |
| 29 | 35,000 | 40,000 | 35,000 |
| 30 | 30,000 | 40,000 | 30,000 |

Max `V = 40k` at `P = 28` only → P\* = 28 without the user.

With user **bid 30, Q = 9999**:

- `V(28) = min(47k + 9999, 40k) = 40,000`
- `V(29) = min(35k + 9999, 40k) = 40,000`
- `V(30) = min(30k + 9999, 40k) = 39,999`

Max tied at 28 and 29 → highest-P tie-break → **P\* = 29**.

Fill walk with you last at price 30:

| level | size | cum |
|-------|------|-----|
| 30 resting | 30,000 | 30,000 |
| 30 user (you) | 9,999 | 39,999 |
| 29 resting leftover | 1 | 40,000 |

You fill 9,999 at clearing 29, buyback is 30, fee 0 → **profit = 9,999 × 1 = 9,999**. Matches `README.md` and the prior note.

Neighbor checks:

- **Q = 10,000**: `V(30) = 40k`, triple tie at 28/29/30 → P\* = 30 → per-unit margin collapses to 0 → **profit = 0**.
- **Q = 9,998**: same P\* = 29, you fill 9,998 → profit 9,998.
- **Bid 29 × large**: V(29) caps at 40k (supply bound); you are last at 29, so you only get `40k − 30k (resting at 30) − 5k (resting at 29) = 5k`. Profit ≤ 5,000.
- **Bid 31+ × large**: pushes P\* to 30 → margin 0.
- **Short side**: every P\* ≤ 30 → `(P\* − 30)` ≤ 0 → non-positive.

`9999` is the strict argmax.

## Ember Mushroom — confirm `bid 17 × 19999 → +77,996.1`

Resting book:

- Bids: `20→43k, 19→17k, 18→6k, 17→5k, 16→10k, 15→5k, 14→10k, 13→7k`
- Asks: `12→20k, 13→25k, 14→35k, 15→6k, 16→5k, 18→10k, 19→12k` (17-ask has size 0 in the snapshot and is intentionally omitted)
- Buyback anchor: `20`, fee `0.10` per unit

Volume curve without the user:

| P | D(P) | S(P) | V(P) |
|----|-------|-------|-------|
| 14 | 96,000 | 80,000 | 80,000 |
| 15 | 86,000 | 86,000 | 86,000 |
| 16 | 81,000 | 91,000 | 81,000 |
| 17 | 71,000 | 91,000 | 71,000 |
| 18 | 66,000 | 101,000 | 66,000 |

Max `V = 86k` at `P = 15`, so P\* = 15 without the user.

With user **bid 17, Q = 19,999**:

- `V(16) = min(81k + 19,999, 91k) = 91,000`
- `V(17) = min(71k + 19,999, 91k) = 90,999`
- `V(15) = 86,000` (unchanged — supply bound)

Strict max at `P = 16` → **P\* = 16**.

Fill walk with you last at price 17:

| level | size | cum |
|-------|------|-----|
| 20 resting | 43,000 | 43,000 |
| 19 resting | 17,000 | 60,000 |
| 18 resting | 6,000 | 66,000 |
| 17 resting | 5,000 | 71,000 |
| 17 user (you) | 19,999 | 90,999 |
| 16 resting leftover | 1 | 91,000 |

Per-unit margin = `20 − 16 − 0.10 = 3.90`. **Profit = 19,999 × 3.90 = 77,996.1**.

Neighbor checks:

- **Q = 20,000 at price 17**: `V(17) = 91k` ties `V(16) = 91k` → P\* = 17 → margin drops to `2.90` → profit 58,000.
- **Q = 19,998 at price 17**: still P\* = 16, fill 19,998 → profit 77,992.2.
- **Bid 18 × 35,000**: drives `V(18) = 101k`, strict max → P\* = 18, margin 1.90, fill bounded at 35k → profit 66,500.
- **Bid 19 × 53,000**: drives `V(19) = 113k`, margin 0.90, fill 53k → profit 47,700.
- **Bid 16 × large**: P\* = 16 but you sit behind 10k resting at 16, fill ≤ 10k → profit ≤ 39,000.
- **Short side**: P\* ≤ 20 always → `(P\* − 20) − 0.10` ≤ −0.10 → non-positive for any positive fill.

`(17, 19999)` is the strict argmax.

## Does "last in line" change the picks?

No. "Last in line" only matters **at your own price level** and only when the level's remaining budget is smaller than `resting + Q`. For both winners:

| product | P\* | V\* | above-your-level demand | resting at your price | your Q | your fill |
|---------|----|-----|-------------------------|-----------------------|--------|-----------|
| Flax (bid 30) | 29 | 40,000 | 0 | 30,000 | 9,999 | 9,999 |
| Mushroom (bid 17) | 16 | 91,000 | 66,000 | 5,000 | 19,999 | 19,999 |

The knife-edge quantities are chosen so that `Q ≤ V* − above − resting`, which means being last costs exactly **zero** fills. Any Q beyond that either (a) still fills fully because the level has slack, or (b) tips the tie-break and flips P\* against you.

Useful predictor before submitting:

```
your_fill = min( Q, max(0, V* − demand_above_your_price − resting_at_your_price) )
```

## Caveats worth keeping in mind

1. **Short side is probably not actionable.** Rules in `round1.md` say the Merchant Guild **buys** any inventory you traded at a fixed price — that only rescues long positions. `ClearingSimulator` still scores shorts as `(P* − anchor) − fee`, which silently assumes a counterparty that doesn't exist in the rules. Treat any `best_short_*` line as an upper bound that likely cannot be realized.
2. **Fee placement for mushroom (0.10).** `ProductParams` charges it on the buyback leg. If the live rules instead charge it on the auction leg (or split 0.05 / 0.05), the optimal `(price, Q)` is unchanged; only the reported profit shifts (worst case `19,999 × 3.80 = 75,996.2` if the fee compounds).
3. **Snapshot drift.** `frozen_books.py` is a manual transcription. A one-unit change to 30-level flax bids or 17-level mushroom bids can move the knife-edge Q by exactly the same amount. Re-run the EV grid if the UI book updates; the `--dense-through` sweep in `ev_enumeration.py` guarantees these integer cliffs are not missed.
4. **Cliff robustness.** The two picks are exactly on the tie-break edge. If you want to pay a small premium for robustness: `flax bid 30 × 9,900` (−99 profit), `mushroom bid 17 × 19,500` (−1,946 profit). Probably not worth it if the live snapshot matches `frozen_books.py`.

## Final submission

- `DRYLAND_FLAX`: **bid 30 × 9,999** → +9,999
- `EMBER_MUSHROOM`: **bid 17 × 19,999** → +77,996.1
- **Manual total ≈ +87,995 XIRECs** (~44% of the 200k round-1 goal in `round1.md`).

No short orders from the grid.