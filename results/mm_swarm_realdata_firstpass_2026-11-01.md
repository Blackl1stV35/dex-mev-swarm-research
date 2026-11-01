# Market-making swarm, real-data first pass (2026-11-01) — inconclusive, confounded, reported honestly

Script: `research/mm_swarm_realdata.py`. Data: real Uniswap v3 USDC/WETH 0.05% pool, 11,599,763 swaps, 2021-05-05 to 2026-09-08 — already fetched and verified by `project-lvr-capture-division-problem14`'s applied bridge (2026-09-08), reused here with no new network calls. Price formula had a reciprocal-direction bug caught by its own sanity assert (0.000294 ≈ "$0.00" at 2dp, not a null value) and fixed before the real run below.

## What this first pass found: a real methodological confound, not a confirmation
Data-driven spike detection (top-5 24h realized-volatility windows, found without being told any dates) landed cleanly on **2021-05-19/20**, the real, well-known mid-May 2021 crypto crash — a genuine sanity check that the detection method works.

But the "calm baseline" comparison is **badly confounded**: all five detected spikes fall in the pool's **first two weeks of existence** (pool created ~2021-05-05), while the calm-window sample was drawn from the calmest quartile of hours across the **full 4.5-year history**, which is dominated by later years when the pool had matured into much deeper, much more stable liquidity. The result — median liquidity 1.94e19 in the calm sample vs 1.3e16-5.3e16 in the spike windows (roughly 1,000-4,000x lower), and per-unit price impact ~1,000x higher in spike windows — is real, but it is largely a **"new, thin pool" effect, not demonstrated to be a "volatility causes dynamic LP flight" effect**. Price impact scales mechanically with liquidity depth regardless of whether that depth is thin because the pool is new or thin because LPs fled a stress event; this pass cannot separate the two.

**The more locally valid comparison (pre-spike vs. during-spike, same era, no cross-era confound) is mixed, not confirming:**

| spike window | liq pre-spike | liq during-spike | change |
|---|---|---|---|
| 2021-05-20 11:15 | 4.33e15 | 1.36e16 | **+214%** (liquidity rose) |
| 2021-05-20 03:15 | 5.28e16 | 1.29e16 | **−76%** (liquidity fell, as hypothesized) |
| 2021-05-20 05:15 | 5.28e16 | 1.29e16 | **−76%** (same window pair, overlapping) |

One of three detected windows shows liquidity *rising* during the spike, directly contradicting the "LPs flee during volatility" premise the whole swarm mechanism (`mm_swarm_model.md` §1-2) depends on. This bounded pass does **not** establish that mechanism — it's inconclusive, and the honest reason is a dataset/era confound, not a refutation or a confirmation.

## Step D (P1 counterfactual): direction holds where it applies, but doesn't test the real trade-off
Where realized depth was lower than the pre-spike level (2 of 3 windows), the simple IL-only proxy shows a floor policy (holding pre-spike depth through the move) would have cost *more* impermanent loss than what was realized — expected, since more capital exposed to a given price move costs more IL in absolute terms. This proxy **does not model fee revenue**, which is the actual point of P1 (does fee capture compensate for the extra IL of not fleeing?) — pool-aggregate data can't answer that without LP-level position data, which this dataset doesn't have.

## Honest bottom line
- The swarm-coordination mechanism in `mm_swarm_model.md` is **not confirmed by this first pass**, and the reason is a specific, named confound (pool-age vs. volatility), not a general failure of the idea.
- A real test needs: (a) spike detection restricted to or weighted toward a mature period of the pool's life (e.g., exclude the first several months), or detrended liquidity relative to a slow-moving baseline rather than a globally-pooled calm sample; (b) more than 3 overlapping/adjacent windows from a single week — the three "spikes" here are really one event seen through 3 overlapping hourly bins, not 3 independent episodes; (c) LP-level (not pool-aggregate) data to actually test the fee-vs-IL trade-off in P1, or at minimum a full fee-revenue accounting layered onto the pool-aggregate IL proxy.
- None of this was attempted in this pass — it was scoped as bounded, per the session's Pro-plan discipline, and stops here with an honest negative/inconclusive finding rather than being re-run until it looks better.
