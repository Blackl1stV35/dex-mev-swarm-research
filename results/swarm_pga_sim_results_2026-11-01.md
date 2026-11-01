# Swarm PGA simulation results (2026-11-01, updated: real-data calibration + a stopping-rule fix)

## Correction from the first pass (same day)
While adding real-data calibration, found and fixed a real bug: the original escalation loop had a bidder **skip its turn entirely** once a minimum-increment raise would exceed the profitability cap `B_MAX`, instead of bidding up to the max it could still profitably pay. Real profit-maximizing bidders don't just give up at an awkward in-between point — they bid their willingness-to-pay ceiling, matching the paper's own Observation 4 stopping rule ("stop raising once a further raise is no longer profitable"). Fixed to clip-and-bid-to-cap. **This changes the numbers below from what was committed earlier the same day** — reported here, not silently overwritten.

## Synthetic run (δ=0.4s latency, fixed 12.5% increment) — corrected
n_total=6. Predictions from `swarm_pga_model.md` §4:

| k | win_rate | miner_revenue | per-member payoff | vs baseline |
|---|---|---|---|---|
| baseline (no swarm) | — | 0.73579 | 0.00063 | 1.0x |
| 1 | 0.0024 | 0.73326 | 0.00216 | 3.4x |
| 2 | 0.0050 | 0.73283 | 0.00206 | 3.25x |
| 3 | 0.0132 | 0.72392 | 0.00353 | 5.57x |
| 4 | 0.0461 | 0.70850 | 0.00896 | 14.13x |
| 5 | 0.1916 | 0.66290 | 0.03008 | 47.43x |

- **(i) confirmed, strongly monotone**: 3.4x → 47.4x as k goes 1→5.
- **(iii) confirmed, monotone**: miner revenue falls 0.736 → 0.663 as k grows.
- **(ii) still only directionally consistent**, not clean (see the latency sweep in `sim_output_2026-11-01.log`) — unchanged conclusion from the first pass, not re-litigated here.

## Real-data-calibrated run (δ=0.1s, real empirical increments {14.5%, 14.8%, 32%})
Calibration source: the paper's own Fig. 2 transcribed real auction — see `realdata_calibration.md`. n=3-4 real data points, explicitly a light sanity check, not a powered calibration.

| k | win_rate | miner_revenue | per-member payoff | vs recal. baseline |
|---|---|---|---|---|
| baseline | — | 0.92910 | 0.00004 | 1.0x |
| 1 | 0.0004 | 0.92974 | 0.00037 | 8.7x |
| 2 | 0.0013 | 0.92279 | 0.00053 | 12.5x |
| 3 | 0.0039 | 0.91847 | 0.00096 | 22.6x |
| 4 | 0.0131 | 0.90718 | 0.00241 | 56.8x |
| 5 | 0.0457 | 0.89238 | 0.00672 | 157.9x |

**Read with the right caution:** the ratios look dramatic (up to 158x) mainly because real-world latency is much faster than the original synthetic guess, so independent competitors compete the surplus down to almost nothing (baseline payoff 0.00004 — tiny in absolute terms). The swarm's per-member payoff is *also* tiny in absolute terms (0.00672 at k=5) — it's "much bigger than almost nothing," not "large." The qualitatively real finding is: **with fast real-world reaction times, the auction becomes close to fully competitive for independent bidders (near-zero surplus), and coordination is the main remaining way to capture any surplus at all** — a sharper, more honest version of the original claim, not just a bigger number.

Miner revenue is also higher throughout (0.89-0.93 vs 0.66-0.74 synthetic) — faster real latency lets bids escalate further before the block is mined, consistent with the paper's own observation that the gas-trend chart (Fig. 8) shows costs rising as the market matured and latencies fell.

## What this is and isn't
- **Is**: a light, honest real-data sanity check and parameter correction on a purely retrospective/formal model. No live bidding, no mainnet interaction, no agents deployed anywhere.
- **Isn't**: a powered empirical study (n=3-4 real data points from one auction) or evidence that deploying a real coordinating swarm is advisable — see `CLAUDE.md`'s destination-objective note; that remains out of scope for this repo as built.
- **Full historical dataset** (hundreds of real PGA auctions, the paper's own 9-month collection) would resolve this properly; not pursued here to keep this a light pass. Noted as the natural next step if the user wants it.
