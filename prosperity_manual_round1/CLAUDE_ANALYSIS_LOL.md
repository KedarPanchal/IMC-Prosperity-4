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