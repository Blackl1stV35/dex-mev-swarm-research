# Option 3: genuine market-making swarm — formal model (before any simulation/data)

Chosen path from the zero-sum/negative-sum finding (see `swarm_pga_model.md` and the session discussion it produced): PGA bidding, however coordinated, only redistributes a fixed pie. This is the alternative — a swarm whose coordination mechanism creates value (tighter effective spreads, more continuous liquidity for real traders) rather than extracting it.

## 0. What makes this different from problem 14 and the PGA swarm
`project-problem14-lvr-capture-division` (market-dynamics-research) proves a real, twice-verified auction-theoretic result for **dividing the LVR-extraction value between a searcher/arbitrageur and the block proposer** — it is still a rent-extraction split, same family as the PGA work, just a different market. It is the wrong foundation to build "genuine value creation" on directly. The relevant piece to reuse is the **underlying LVR cost formula** it draws on (Milionis, Moallemi, Roughgarden, Zhang — "Automated Market Making and Loss-Versus-Rebalancing," a published closed-form result) [**R, recalled from training, NOT independently re-derived or verified this session** — same discipline problem 14 itself used for this external result; flag before citing formally].

## 1. The LP's actual problem (not the arbitrageur's)
For a constant-function AMM pool with liquidity depth `L` near the current price and asset volatility `σ`, the continuous-time LVR rate (the pool's expected loss to informed arbitrageurs, the "cost of the free convexity option" every passive LP gives away) is approximately:

```
LVR_rate(t) ≈ (σ²/8) · L(t)
```

Fee revenue to an LP providing share `ℓ_i(t)/L(t)` of total depth, at volume `V(t)` and fee rate `φ`, is approximately `φ·V(t)·ℓ_i(t)/L(t)`.

**The myopic individual-LP failure mode** (well documented empirically in Uniswap v3 LP studies, not re-derived here): during high-volatility windows, LVR_rate rises (scales with `σ²`) while an individual LP's perceived fee compensation doesn't rise proportionally fast enough, so LPs withdraw depth exactly when continuous liquidity is most valuable to real traders — a coordination failure, not a strategic extraction game. This is the lever a swarm can act on.

## 2. Swarm mechanism (the genuinely new part — not yet proven, this is what needs cracking)
A swarm of `k` LPs pre-commits to:
(a) a joint minimum aggregate depth floor `L_min` maintained even during a volatility spike that would make any single member want to withdraw individually, and
(b) **pooling** fee revenue and LVR losses pro-rata across the `k` members, so no single member bears a disproportionate LVR hit for honoring the commitment (a mutual/insurance structure, not a non-competition cartel — this is the structural difference from the PGA swarm, which is why it is not automatically zero-sum: the swarm is not reducing the number of real competitors for a fixed opportunity, it is **supplying a public good** — continuous liquidity — that benefits every trader, swarm member or not).

## 3. Proposition to test (pre-registered here, before any data is touched)
Relative to `k` uncoordinated LPs each acting myopically:
- **(P1, swarm-side)**: the coordinated swarm's risk-adjusted (Sharpe-like) per-member return is higher, because pooling avoids each member's own "withdraw during the spike, re-enter after, buy-high-sell-low" pattern.
- **(P2, trader-side, the actual value-creation claim)**: realized effective spread / slippage for real (non-swarm) traders is measurably lower during high-volatility windows when the swarm maintains `L_min`, compared to windows/pools without such coordination.

**P2 is the whole point** — if it doesn't hold, this is not a value-creating mechanism and the "positive-sum" claim fails, the same way the PGA predictions were allowed to fail honestly rather than be forced. Both P1 and P2 are testable against real Uniswap v3 data, not just synthetic simulation — `project-lvr-capture-division-problem14`'s applied-bridge work (2026-08-15) already established **real, accessible Uniswap v3 subgraph data exists for this** (USDC/WETH 0.05% pool, 26,018 swaps/week, continuous history from 2021-05-05, verified against Binance to 0.1%). That data source is the natural one to reuse here rather than resample from scratch.

## 4. What's NOT done yet, and why this turn stops here
- The LVR formula and the swarm proposition above are stated, not yet independently re-derived/proven (the `[R]` flag on the formula is real — it needs the same crack-math-first treatment problem 14 gave its own starting formula before anything is simulated or fit to data).
- Pulling real Uniswap v3 data (even reusing the problem-14 bridge's data source) and testing P1/P2 is a **heavy job** by the Pro-plan discipline set earlier this session (API/subgraph calls, a volatility-window detection pass, effective-spread measurement — comparable in scope to the problem-14 applied bridge itself, which took a dedicated multi-stage session). Not started without checking session headroom first.
- Scope added to `CLAUDE.md` as research line 2; destination-objective boundary (no live LP capital deployed) applies here exactly as it does to the PGA line.
