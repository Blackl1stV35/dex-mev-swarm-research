"""Option B backtest (2026-11-02): a solo full-range (v2-equivalent) LP, $1 starting capital,
held constant (never withdrawn, never rebalanced), in the real Uniswap v3 USDC/WETH 0.05% pool,
2021-05-05 to 2026-09-08. Real price, real liquidity, real per-swap fees -- no new fetch.

Scope, stated plainly:
  - FULL-RANGE assumption (v2-equivalent). The real LPs whose liquidity this pool's `liq` field
    reflects mostly run CONCENTRATED ranges (more fee-dense, but exposed to range-exit risk this
    backtest does not model). Full-range is the simplest, most defensible first backtest: always
    earning some fee, never zero from exiting a range, standard well-known IL formula applies
    cleanly throughout. A concentrated-range version is a materially bigger separate task, not
    attempted here.
  - IL formula: standard constant-product identity, position_value(t)/position_value(0) =
    sqrt(P_t/P_0), exact for a full-range position, independent of position size.
  - Fee share: this LP's liquidity contribution l0 is fixed at entry to represent exactly $1 of
    value (derived from TVL = 2*L/(sqrtP*1e6), itself derived from the pool's raw reserves
    identity -- not assumed, checked against a plausible-TVL sanity assert below). Fee share at
    each swap = l0 / L(t), so it falls as the REAL pool grows (more LPs join) and rises if the
    real pool's liquidity shrinks (LPs leave) -- exactly the mechanism tested in the earlier
    clean test, now actually monetized into a P&L curve instead of just a yield ratio.

No live trading, no real capital, read-only analysis of historical public data.
"""
import json
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DATA = r"D:\market-dynamics-research\data\uniswap_v3_lp\USDC_WETH_005"
OUT_DIR = r"D:\dex-mev-swarm-research\results"
FEE_RATE = 0.0005

print("Loading real swap data (no network, already-fetched)...")
ts = np.load(os.path.join(DATA, "ts.npy"))
sqrtp = np.load(os.path.join(DATA, "sqrtp.npy"))
liq = np.load(os.path.join(DATA, "liq.npy"))
amount1 = np.load(os.path.join(DATA, "amount1.npy"))
n = len(ts)
print(f"  {n:,} real swaps, {np.datetime64(int(ts[0]), 's')} to {np.datetime64(int(ts[-1]), 's')}")

price = 1e12 / (sqrtp ** 2)  # USDC per WETH, verified formula
assert 500 < price[0] < 10000, f"price sanity check failed: {price[0]}"
fee_usd = np.abs(amount1) * price * FEE_RATE

# TVL identity (derived, not assumed): at the current price, a full-range position's two legs
# are of EQUAL value (x_raw * price_of_x_in_y = y_raw, the definition of marginal price), so
# TVL_USD = 2 * x_human = 2 * (L/sqrtP_raw)/1e6 (USDC has 6 decimals). sqrtp IS sqrtP_raw here
# (verified: price = 1e12/sqrtp^2 already gives the correct human $/ETH figure).
tvl_usd = 2 * liq / (sqrtp * 1e6)
assert 1e3 < tvl_usd[0] < 1e10, f"TVL sanity check failed: ${tvl_usd[0]:,.0f} at first swap (expected $1k-$10B range)"
print(f"  TVL sanity check: ${tvl_usd[0]:,.0f} at first swap, ${np.median(tvl_usd):,.0f} median (plausible range OK)")

# our hypothetical LP's liquidity contribution, calibrated to be worth exactly $1 at entry
l0 = sqrtp[0] * 5e5  # from TVL=2*L/(sqrtP*1e6)=1 => L = sqrtP*1e6/2
fee_share = l0 / liq  # varies over time with the REAL pool's liquidity path
fee_earned = fee_share * fee_usd
cum_fees = np.cumsum(fee_earned)

r_t = price / price[0]
position_value_ex_fees = np.sqrt(r_t)  # standard full-range IL identity, scale-invariant
nav = position_value_ex_fees + cum_fees

hodl_5050 = 0.5 + 0.5 * r_t
hodl_weth = r_t
hodl_usdc = np.ones_like(r_t)

# --- resample to daily for charting ---
df = pd.DataFrame({"ts": ts, "nav": nav, "cum_fees": cum_fees, "price": price,
                    "hodl_5050": hodl_5050, "hodl_weth": hodl_weth})
df["date"] = pd.to_datetime(df["ts"], unit="s").dt.floor("D")
daily = df.groupby("date").last()  # end-of-day values

final = dict(
    final_nav=float(nav[-1]), final_cum_fees=float(cum_fees[-1]),
    final_position_value_ex_fees=float(position_value_ex_fees[-1]),
    final_hodl_5050=float(hodl_5050[-1]), final_hodl_weth=float(hodl_weth[-1]),
    final_price=float(price[-1]), initial_price=float(price[0]),
    total_return_pct=100 * (nav[-1] - 1), hodl_5050_return_pct=100 * (hodl_5050[-1] - 1),
    hodl_weth_return_pct=100 * (hodl_weth[-1] - 1),
    outperformance_vs_hodl5050_pct=100 * (nav[-1] - hodl_5050[-1]),
)
print("\n=== Final result, full 2021-05-05 to 2026-09-08 ===")
print(f"  LP strategy NAV (from $1):        ${nav[-1]:.3f}  ({final['total_return_pct']:+.1f}%)")
print(f"    of which fee income:            ${cum_fees[-1]:.3f}")
print(f"    of which price exposure (IL-adj):${position_value_ex_fees[-1]:.3f}")
print(f"  HODL 50/50 benchmark:              ${hodl_5050[-1]:.3f}  ({final['hodl_5050_return_pct']:+.1f}%)")
print(f"  HODL 100% WETH benchmark:          ${hodl_weth[-1]:.3f}  ({final['hodl_weth_return_pct']:+.1f}%)")
print(f"  LP strategy vs HODL 50/50:         {final['outperformance_vs_hodl5050_pct']:+.1f}pp")

with open(os.path.join(OUT_DIR, "mm_backtest_2026-11-02.json"), "w", encoding="utf-8") as fh:
    json.dump(final, fh, indent=2)

# --- chart ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})

ax1.plot(daily.index, daily["nav"], color="#2b5c8a", lw=1.8, label="Full-range LP strategy (fees + IL)")
ax1.plot(daily.index, daily["hodl_5050"], color="#c9742c", lw=1.4, ls="--", label="HODL 50/50 USDC+WETH")
ax1.plot(daily.index, daily["hodl_weth"], color="#4f8a3b", lw=1.2, ls=":", label="HODL 100% WETH")
ax1.axhline(1.0, color="#999999", lw=0.8)
ax1.set_yscale("log")
ax1.set_ylabel("NAV, from $1 (log scale)")
ax1.set_title("Option B backtest: full-range USDC/WETH LP vs. HODL benchmarks, real data 2021-2026")
ax1.legend(fontsize=9, loc="upper left")
ax1.grid(alpha=0.3, which="both")

ax2.plot(daily.index, daily["cum_fees"], color="#8c4fa0", lw=1.8)
ax2.set_ylabel("Cumulative fee income\n(from a $1 LP position, USD)")
ax2.set_xlabel("Date")
ax2.grid(alpha=0.3)

fig.tight_layout()
chart_path = os.path.join(OUT_DIR, "mm_backtest_2026-11-02.png")
fig.savefig(chart_path, dpi=130)
print(f"\nwritten: {chart_path}")
