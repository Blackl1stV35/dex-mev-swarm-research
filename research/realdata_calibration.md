# Real-data calibration (light pass, 2026-11-01)

Source: the paper's own **Figure 2** (page 5), a real recorded PGA between two competing bots on Ethereum mainnet, transcribed directly from the published table (timestamps, Gwei bids, tx hashes). This is a single illustrative real auction the paper's authors themselves selected to show, not their full multi-month dataset (that lives in their GitHub repo, hundreds of GB of raw mempool observations — fetching it is a heavier task, not attempted in this light pass; noted as a further upgrade option below).

## Transcribed data (bot A = `0x6BEc...6542`, nonce 1453; bot B = `0xb8D7...7a3f`, nonce 1512)
| t (s) | bidder | bid (Gwei) |
|---|---|---|
| 0.000 | A | 25.10 |
| 1.593 | B | 25.00 |
| 1.624 | A | 28.75 |
| 1.679 | B | 28.81 |
| … | … | … (38 more bids omitted in the paper's own table) |
| 4.949 | A | 134.02 |
| 5.599 | B | 133.76 |
| … | … | … |
| 13.383 | A | 5834.77 |
| 13.416 | B | 7716.48 |
| 13.462 | A | 7701.09 |
| 13.759 | B (mined) | 8856.24 |

## What this corrects in the original simulation
1. **Latency parameter was wrong by 4-13x.** The original `swarm_pga_sim.py` used `outside_latency_mean = 0.4s`, taken from misreading the paper's Fig. 14 caption — that 0.4s is `t`, the **mean game-interval length** for the cooperative-strategy numerical example, not the latency `δ`. The paper's own stated latency parameter for that same example is **δ = 0.1s** (Fig. 14 caption). The real consecutive-response gaps visible in the Figure 2 table are **0.031s, 0.055s, 0.033s, 0.046s** — i.e. genuine reaction latency in this real auction was 30-55ms, even faster than the paper's own δ=0.1s modeling parameter. Recalibrated run below uses δ=0.1s (the paper's own stated value, a conservative middle ground given the observed range).
2. **Fixed 12.5% bid increment doesn't match the one real late-stage jump visible.** Consecutive real steps give ratios of **1.1454 (14.5%), 1.1477 (14.8%)** — close to the paper's stated Parity-client minimum (12.5%) — but one real step, 5834.77 → 7701.09, is a **1.3199 (32%) jump**, well above the minimum. This suggests at least one bot sometimes bids a large multiple of the minimum rather than minimum+ε, possibly a "scare off the opponent" move not modeled by pure reactive counterbidding. Recalibrated run samples the increment from the empirical set {0.1454, 0.1477, 0.32} rather than a fixed 0.125, as an honest (if thin-sample) correction — this is 3 data points, not a distribution fit; flagged as low-confidence.

## Honest limits of this calibration
- n=3 to 4 real latency observations and n=3 real increment observations, from **one** auction. This is a sanity check and a parameter correction, not a statistically powered calibration.
- The full historical dataset (hundreds of PGA auctions over 9 months, per the paper's §IV-A) would give a real empirical distribution instead of a handful of points — that is the natural next step if more rigor is wanted, and was not pursued here to keep this a light pass.
- See `swarm_pga_sim.py`'s `recalibrated_run()` for the updated parameters and `results/swarm_pga_sim_results_2026-11-01.md` (appended section) for the before/after comparison.
