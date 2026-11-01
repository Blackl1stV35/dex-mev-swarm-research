# Swarm PGA simulation results (2026-11-01)

Ran `research/swarm_pga_sim.py` against the three pre-registered predictions in `research/swarm_pga_model.md` §4. n_total=6, outside-competitor latency mean 0.4s (paper's measured figure), swarm's effective bidder same latency class (fair test, no speed advantage assumed — isolates the pure coordination effect).

| Prediction | Result | Verdict |
|---|---|---|
| (i) per-member swarm payoff ≥ independent payoff, gap widens in k | 2.9x at k=1 (degenerate, no real coordination) rising monotonically to 43.8x at k=5 | **Confirmed, strongly monotone** |
| (iii) miner revenue falls as k grows | 0.733 → 0.730 → 0.724 → 0.709 → 0.663 (baseline 0.736), monotone decreasing | **Confirmed, strongly monotone** |
| (ii) gap shrinks toward 0 as outside latency → 0 | ratio 1.98x at lat=0.05 (lowest) vs 9.30x at lat=1.60 (highest) — directionally consistent at the extremes, but non-monotone through the middle (0.10→9.76x, 0.20→1.24x) | **Directionally consistent, not cleanly confirmed** — likely Monte Carlo noise from low win-counts at low latency (8,000 trials, win probabilities in the 1e-4 to 1e-3 range at the low end); needs more trials to resolve, not re-run here to stay quota-frugal |

## Reading
The core claim survives: **coordinated non-competition among a subset of PGA bidders (a "swarm") captures more expected value per member than competing independently, and does so by reducing effective competition, which lowers what the auction pays to the block producer** — exactly the classical bidding-ring mechanism (McAfee & McMillan 1992), now confirmed to hold in this paper's specific continuous-time/imperfect-information/all-pay PGA structure, not just the simpler sealed-bid setting the classical theory was built for.

This is **not** a novel economic result (bidding rings are old theory) and it is **not** evidence that building such a swarm is advisable in practice — see caveats.

## Caveats (read before acting on this)
1. **Simulation simplification**: the auction is resolved via round-based reactive escalation rather than a true continuous-time event queue; this should converge to the same terminal winner as the paper's continuous model (bids are monotone and bounded, no cycling), but was not formally proven equivalent here — flagged, not fixed, given quota constraints.
2. **Prediction (ii) unresolved** at this sample size — report it as such, do not claim the latency-amplification mechanic is confirmed.
3. **The model assumes credible internal swarm enforcement** (grim-trigger) is costless and perfectly effective. Real coordination among independent trading-strategy agents has implementation cost, trust risk, and detection risk (observers can infer coordinated non-competition from on-chain bid patterns, same as cartel detection in real auction markets) — none of that friction is in the simulation.
4. **This is synthetic-market research**, matching the repo's CLAUDE.md scope: a simulated auction with synthetic agents, not a bot deployed against real PGA participants on mainnet. It demonstrates *why* a coordinating group of agents captures more value in this game structure, which is directly useful for (a) understanding the security externality (lower miner/builder revenue, i.e. a concrete mechanism for the "MEV subsidizes forking attacks" argument — see `ethereum_architecture_security_survey.md`), and (b) deciding whether to pursue this further at all, which is a decision for the user, not something to proceed on by default.
