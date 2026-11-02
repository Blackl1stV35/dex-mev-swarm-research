# LVR-aware LP hedging/insurance: startup-route validation (2026-11-02)

CLOSED at the design stage. The base cost formula is real and now independently verified; no
candidate hedge/insurance mechanism survived its own honest value-creation check.

## 1. Formula verification (PASSED, independently derived + primary-source confirmed)

`LVR_rate(t) ≈ (σ²/8)·V(t)` is correct, where `V(t)` must be read as the pool's current dollar
depth (`V(P) = 2L√P` for full-range constant-product, not the raw on-chain invariant constant
`L`) -- a factor-of-`2√P` unit error is easy to make plugging raw Uniswap `liquidity` directly
into the formula. Independently re-derived via envelope theorem + Ito (two routes: continuous
quadratic-variation and the paper's discrete price-slippage argument, both agreeing), then
cross-checked line-by-line against the primary source (Milionis, Moallemi, Roughgarden, Zhang,
arXiv:2208.06046v4, Theorem 1 / Example 3) -- exact match, including the σ²/8 constant.

Real scope limits established, directly relevant to any product built on it:
- It is a **frictionless, continuous-time upper bound**, not the realized net LP cost: real fee
  income, discrete-block arbitrage frictions, and MEV/gas-auction competition for the arb trade
  (this repo's own closed PGA-swarm result: constant-sum including the proposer, negative-sum
  among searchers) all reduce the realized number below this ceiling.
- For **concentrated** (not full-range) Uniswap v3 positions, loss-per-dollar-of-capital is
  unbounded as the range narrows -- exactly where real LPs sit to maximize fee APR. Any pricing
  built on `σ²/8` alone, ignoring range width, will be badly mis-calibrated for the real market.

## 2. Mechanism design (FAILED -- 0 of 3 candidates survived their own check)

Three independent designs were formalized and each checked against the same bar that closed the
PGA-swarm and mm-swarm lines in this repo: does it create real value, or does it just redistribute
/ relabel the existing LVR cost?

| Design | Counterparty | Feasibility | Survives? |
|---|---|---|---|
| LVR reinsurance swap (pooled, IV-struck) | External crypto options/vol dealers | 3/10 | No |
| On-chain LVR variance swap + cat-bond reinsurance | Diversified vol-trading/cat-bond pool | 3/10 | No |
| Continuous long-variance overlay (gamma-matching) | Options/variance-swap dealers (Deribit-style) | 2/10 | No |

**All three fail for the same underlying reason**, a direct generalization of the finding that
already closed the mm_swarm coordination line: crypto volatility spikes are systemic, not
idiosyncratic. The whole insurance/hedging case for each design rests on the external
counterparty being genuinely diversified away from this specific pool's risk -- but realized AMM
volatility and the external vol-dealer's book are both driven by the same crypto-wide beta factor,
and this repo's own mm_swarm result already established that the episodes where LVR actually
spikes hardest (Luna 2022-05, FTX 2022-11) are exactly systemic, correlated crises, not generic
volatility. The "diversified vol desk" is not diversified from the risk it is being asked to
insure, precisely when a claim would be made. A rational dealer prices that correlation in ex ante,
so the premium converges to roughly the true expected cost plus the dealer's margin -- not a
genuine risk-premium capture.

Secondary, independent flaws found per design:
- **Reinsurance swap**: reduces to "retail insurance for mild vol that works, catastrophe
  insurance for the case LPs actually care about that doesn't."
- **On-chain variance swap**: a "double-dip" trap if the counterparty is or correlates with the
  actual arbitrageur extracting this pool's LVR (the cheapest-to-source counterparty) -- becomes a
  costless pass-through with a fee skimmed off, i.e. problem14's extraction-split mechanism again,
  which this task explicitly set out to avoid. Also: a sophisticated LP can already approximately
  replicate this with listed exchange variance swaps today, so the novel value left over is thin
  (UX/automation, not a new risk-transfer mechanism).
- **Gamma/variance overlay**: the literal "hedge with a perp" sub-design is formally shown to
  cancel the wrong Greek (pure delta-hedging removes price noise but leaves the LVR drag term,
  which comes from gamma, completely intact). The corrected gamma/variance version still fails the
  same correlated-tail test, and competes against an already-liquid, competitively-priced listed
  options/variance-swap market (Deribit etc.) with no structural edge for a new entrant.

## 3. Backtest / adversarial verification

Not run. The workflow's own gate (no empirical test on a mechanism that already failed its formal
value-creation check) triggered correctly -- skipping an empirical test on a structurally-broken
design, consistent with this session's own ["crack math first" discipline](../../CLAUDE.md), even
though that specific standing rule was revoked as a mandatory gate immediately afterward.

## Verdict

**NOT a viable startup route as scoped.** The underlying cost (LVR) is real and now rigorously
confirmed; a hedging/insurance *product* built directly on it does not clear this project's own
value-creation bar, for the same systemic-correlation reason that already closed the
market-making-coordination-swarm line. The one candidate not fully eliminated: a genuinely
**thin UX/automation layer** connecting LPs to the *already-existing*, liquid options/variance-swap
market (noted as a residual possibility under the on-chain variance-swap design) -- real, but a
modest intermediation business, not a novel value-creating mechanism, and not what was being
tested here.

Of the three routes discussed for a blockchain-trading-system startup (cross-venue arbitrage,
AMM liquidity provision, MEV-protected execution routing), **Option B (AMM LP as a solo desk
strategy, already backtested with a real positive edge) remains the only thread with a confirmed
positive result.** This closes the "novel" LVR-hedge/insurance route.
