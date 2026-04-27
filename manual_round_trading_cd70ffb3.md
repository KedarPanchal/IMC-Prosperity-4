---
name: Manual Round Trading
overview: Build a balanced expected-value manual order plan for the Aether Crystal options round using the published GBM assumptions, visible bid/ask prices, and expanded exotic contract terms.
todos:
  - id: enter-orders
    content: Enter the recommended buy/sell sides and volumes in the manual challenge table.
    status: pending
  - id: verify-ticket
    content: Before submitting, confirm no unintended rows have side/volume filled.
    status: pending
  - id: optional-risk-adjust
    content: If choosing a more aggressive profile, increase only the `AC_50_CO` and `AC_40_BP` shorts, not the tiny-edge vanilla shorts.
    status: pending
isProject: false
---

# Manual Round Trading Plan

## Recommendation

Submit this balanced ticket:

- `AC_50_P_2`: **Buy 50** at ask `9.75`
- `AC_50_C_2`: **Buy 50** at ask `9.75`
- `AC_45_KO`: **Buy 500** at ask `0.175`
- `AC_50_CO`: **Sell 25** at bid `22.2`
- `AC_40_BP`: **Sell 25** at bid `5.0`
- Leave all other contracts blank / no trade

This is the balanced version. If you decide to maximize expected value more aggressively, increase `AC_50_CO` and `AC_40_BP` shorts from 25 each toward the full displayed volume of 50 each. I would not do that unless you are comfortable with materially larger downside in adverse simulations.

## Why These Trades

The model uses the round assumptions in `[.cursor/rules/round4.md](/Users/Shalya/Desktop/Hackathons%202025-2026/IMC%20Prosperity%2026/.cursor/rules/round4.md)`: zero-drift GBM, annualized volatility `251%`, `4` steps per trading day, and discrete barrier observation.

Estimated single-unit fair values versus market:

- `AC_50_P_2`: fair about `9.871`, ask `9.75`, buy edge about `+0.121`
- `AC_50_C_2`: fair about `9.871`, ask `9.75`, buy edge about `+0.121`
- `AC_45_KO`: fair about `0.206`, ask `0.175`, buy edge about `+0.031`
- `AC_50_CO`: fair about `21.88`, bid `22.2`, sell edge about `+0.32`
- `AC_40_BP`: fair about `4.768`, bid `5.0`, sell edge about `+0.232`

Trades skipped:

- `AC`: mid is fair, spread is a cost.
- 3-week vanilla puts/calls are mostly at or very near fair; the small apparent `AC_60_C` short edge is too tiny for the tail risk.
- `AC_35_P`, `AC_40_P`, `AC_45_P`, `AC_50_P`, and `AC_50_C` do not offer enough edge after crossing the spread.

## Risk Logic

The long 2-week `50` call and put form an underpriced ATM straddle, which is clean positive expected value and benefits from the very high volatility assumption. Buying `AC_45_KO` is also positive expected value and has limited loss, though it often expires worthless because the `35` barrier is frequently touched.

The chooser and binary put appear overpriced, so selling them has positive expected value. However, both introduce downside: the binary can lose when `S_T < 40`, and the chooser short can lose badly on large directional moves after the choose date. For a balanced risk profile, sell only half the available volume.

A rough simulation of the balanced ticket, including the `3000` contract-size multiplier, produced expected PnL around `+130k`, with a wide distribution. The aggressive full-short version had higher expected PnL around `+176k`, but much worse left-tail behavior.

## Assumptions

- Current `AETHER_CRYSTAL` spot is the displayed mid-price, approximately `50`.
- Buying crosses the ask; selling crosses the bid.
- The displayed `T + 14/21` and `T + 21` map to the rule file’s 2-week / 3-week trading horizons: `10` and `15` trading days, not literal calendar days.
- `AC_40_BP` pays fixed `10` if final `AETHER_CRYSTAL < 40`; otherwise `0`.
- `AC_45_KO` is a strike `45` put with barrier `35`, knocked out only if a discrete simulated price is below `35` before expiry.
- There is no dynamic hedging or resubmission after the order; all positions are held to expiry and marked against simulated fair payoff.
- Objective is balanced expected PnL, not minimum variance or maximum expected PnL at any cost.