"""Proper clean test (2026-11-01), fixing all three confounds named in the first pass:

  1. Pool-age confound: liquidity is now compared to a CAUSAL rolling baseline (30-day
     trailing median), not a globally-pooled "calm" sample dominated by later, mature years.
  2. Single-event confound: volatility episodes are now detected with a minimum separation
     (45 days) across the FULL 2021-2026 history, not 3 overlapping hourly bins of one week.
  3. Modeling error found while building this: the first pass's IL proxy incorrectly scaled
     with WHOLE-POOL liquidity, as if the whole pool were one LP's capital. An individual LP's
     impermanent loss depends on THEIR OWN capital and the price move, not on other LPs'
     capital. What total pool liquidity actually controls is each LP's FEE-SHARE split. This
     version tests the correct quantity: does an LP's fee yield per unit of their own capital
     rise when other LPs flee (total pool liquidity drops) during a volatility spike?

Reuses the same real Uniswap v3 USDC/WETH data, no new fetch. Read-only, no live trading.
"""
import json
import os

import numpy as np
import pandas as pd

DATA = r"D:\market-dynamics-research\data\uniswap_v3_lp\USDC_WETH_005"
OUT_DIR = r"D:\dex-mev-swarm-research\results"
FEE_RATE = 0.0005
BASELINE_DAYS = 30
MIN_SEPARATION_DAYS = 45
TOP_K_EPISODES = 6

print("Loading real swap data (no network, already-fetched)...")
ts = np.load(os.path.join(DATA, "ts.npy"))
sqrtp = np.load(os.path.join(DATA, "sqrtp.npy"))
liq = np.load(os.path.join(DATA, "liq.npy"))
amount1 = np.load(os.path.join(DATA, "amount1.npy"))
n = len(ts)
print(f"  {n:,} real swaps, {np.datetime64(int(ts[0]), 's')} to {np.datetime64(int(ts[-1]), 's')}")

price = 1e12 / (sqrtp ** 2)  # USDC per WETH (verified formula, see mm_swarm_realdata.py comment)
assert 500 < price[0] < 10000, f"price sanity check failed: {price[0]}"
fee_usd = np.abs(amount1) * price * FEE_RATE  # fee collected on each swap, in USD (WETH leg x price x fee rate)
# (fee is charged on the input token; using the WETH leg x price as a USD-notional proxy for
#  swap size is an approximation when USDC is the input, flagged -- the two sides are economically
#  close since price is the USDC/WETH exchange rate, so this under/overstates fee_usd by at most
#  the fee rate itself, 5bps, negligible for this purpose)

# --- hourly series (real time, causal-safe) ---
hours = (ts - ts[0]) // 3600
n_hours = int(hours[-1]) + 1
bin_edges = np.searchsorted(hours, np.arange(n_hours + 1))
hourly_price = np.full(n_hours, np.nan)
hourly_liq = np.full(n_hours, np.nan)
hourly_fees = np.zeros(n_hours)
for h in range(n_hours):
    lo, hi = bin_edges[h], bin_edges[h + 1]
    if hi > lo:
        hourly_price[h] = price[hi - 1]
        hourly_liq[h] = liq[hi - 1]
        hourly_fees[h] = fee_usd[lo:hi].sum()
mask = ~np.isnan(hourly_price)
idx = np.where(mask, np.arange(n_hours), 0)
np.maximum.accumulate(idx, out=idx)
hourly_price = hourly_price[idx]
hourly_liq = hourly_liq[idx]  # fill quiet hours with last-known liq (no trade -> no change)

# --- Fix 1: causal rolling baseline, relative liquidity (de-confounds pool age) ---
liq_series = pd.Series(hourly_liq)
baseline = liq_series.rolling(window=BASELINE_DAYS * 24, min_periods=24).median()
rel_liq = (liq_series / baseline).values  # 1.0 = at recent normal; <1 = below recent normal

log_ret = np.diff(np.log(hourly_price))
WIN = 24
roll_vol = np.array([np.std(log_ret[max(0, i - WIN):i + 1]) for i in range(len(log_ret))])

# --- Fix 2: independent episodes, minimum separation ---
print(f"\nDetecting top {TOP_K_EPISODES} volatility episodes, >= {MIN_SEPARATION_DAYS}d apart, full 2021-2026 history...")
candidates = np.argsort(roll_vol)[::-1]
episodes = []
min_sep_hours = MIN_SEPARATION_DAYS * 24
for c in candidates:
    if baseline.iloc[c] != baseline.iloc[c] or c < BASELINE_DAYS * 24:  # need a real baseline, skip pool infancy for the baseline itself
        continue
    if all(abs(c - e) >= min_sep_hours for e in episodes):
        episodes.append(int(c))
    if len(episodes) >= TOP_K_EPISODES:
        break
episodes.sort()
for e in episodes:
    print(f"  {np.datetime64(int(ts[0] + e * 3600), 's')}: vol={roll_vol[e]:.4f}, rel_liq={rel_liq[e]:.3f}")

# --- Fix 3: correct quantity -- fee yield per unit of OWN capital, which scales as 1/L_total ---
print("\n=== Corrected mechanism test: relative liquidity + fee-yield-per-unit-capital, pre vs during spike ===")
results = []
for e in episodes:
    win_lo, win_hi = max(0, e - 12), min(n_hours - 1, e + 12)
    pre_lo, pre_hi = max(0, e - 24 - 12), max(0, e - 12)
    rel_liq_pre = float(np.nanmedian(rel_liq[pre_lo:pre_hi])) if pre_hi > pre_lo else float("nan")
    rel_liq_during = float(np.nanmedian(rel_liq[win_lo:win_hi + 1]))

    # P2: trader-side effective price impact, same de-confounded episodes (per-swap, using the
    # actual swap records in these hour ranges, not the hourly-binned series).
    t_win_lo, t_win_hi = ts[0] + win_lo * 3600, ts[0] + (win_hi + 1) * 3600
    t_pre_lo, t_pre_hi = ts[0] + pre_lo * 3600, ts[0] + pre_hi * 3600
    sel_during = (ts >= t_win_lo) & (ts < t_win_hi)
    sel_pre = (ts >= t_pre_lo) & (ts < t_pre_hi)
    impact_during = impact_pre = float("nan")
    if sel_during.sum() > 5:
        p_d = price[sel_during]
        impact_during = float(np.median(np.abs(np.diff(np.log(p_d))) / (np.abs(amount1[sel_during][1:]) + 1e-9)))
    if sel_pre.sum() > 5:
        p_p = price[sel_pre]
        impact_pre = float(np.median(np.abs(np.diff(np.log(p_p))) / (np.abs(amount1[sel_pre][1:]) + 1e-9)))
    # fee yield per unit capital proxy = total fees in window / median total pool liquidity in window
    # (an LP holding a FIXED own-capital X earns X/L_total(t) * fees(t); yield-per-unit = fees/L_total,
    #  independent of X, so this is the right comparable quantity)
    L_during = float(np.nanmedian(hourly_liq[win_lo:win_hi + 1]))
    L_pre = float(np.nanmedian(hourly_liq[pre_lo:pre_hi])) if pre_hi > pre_lo else float("nan")
    fees_during = float(hourly_fees[win_lo:win_hi + 1].sum())
    fees_pre = float(hourly_fees[pre_lo:pre_hi].sum()) if pre_hi > pre_lo else float("nan")
    yield_during = fees_during / L_during if L_during > 0 else float("nan")
    yield_pre = fees_pre / L_pre if L_pre and L_pre > 0 else float("nan")
    r = dict(
        date=str(np.datetime64(int(ts[0] + e * 3600), "s")),
        rel_liq_pre=rel_liq_pre, rel_liq_during=rel_liq_during,
        liquidity_fled_relative=bool(rel_liq_during < rel_liq_pre * 0.9) if rel_liq_pre == rel_liq_pre else None,
        fee_yield_per_unit_capital_pre=yield_pre, fee_yield_per_unit_capital_during=yield_during,
        yield_rose_when_liquidity_fled=bool(yield_during > yield_pre) if yield_pre == yield_pre and yield_pre > 0 else None,
        median_price_impact_pre=impact_pre, median_price_impact_during=impact_during,
        trader_impact_rose=bool(impact_during > impact_pre) if impact_pre == impact_pre else None,
    )
    results.append(r)
    print(f"  {r['date']}: rel_liq pre={rel_liq_pre:.3f} during={rel_liq_during:.3f} "
          f"(fled={r['liquidity_fled_relative']}) | fee-yield/unit pre={yield_pre:.3e} during={yield_during:.3e} "
          f"(rose={r['yield_rose_when_liquidity_fled']}) | trader impact pre={impact_pre:.3e} during={impact_during:.3e} "
          f"(rose={r['trader_impact_rose']})")

n_fled = sum(1 for r in results if r["liquidity_fled_relative"])
n_yield_rose = sum(1 for r in results if r["yield_rose_when_liquidity_fled"])
n_valid = sum(1 for r in results if r["liquidity_fled_relative"] is not None)
n_impact_rose = sum(1 for r in results if r["trader_impact_rose"])
n_fled_and_impact_rose = sum(1 for r in results if r["liquidity_fled_relative"] and r["trader_impact_rose"])
print(f"\nAcross {len(episodes)} independent, separated real episodes (de-confounded for pool age):")
print(f"  relative liquidity fell during the spike: {n_fled}/{n_valid}")
print(f"  fee yield per unit capital rose during the spike: {n_yield_rose}/{len(results)}")
print(f"  trader price impact rose during the spike: {n_impact_rose}/{len(results)}")
print(f"  of the {n_fled} episodes where liquidity fled, {n_fled_and_impact_rose} also show higher trader impact (P2 test)")

out = dict(n_swaps=int(n), episodes=episodes, results=results,
           n_episodes_liquidity_fled=n_fled, n_episodes_valid=n_valid,
           n_episodes_yield_rose=n_yield_rose, n_episodes_impact_rose=n_impact_rose,
           n_episodes_fled_and_impact_rose=n_fled_and_impact_rose, n_episodes_total=len(results),
           params=dict(baseline_days=BASELINE_DAYS, min_separation_days=MIN_SEPARATION_DAYS, top_k=TOP_K_EPISODES))
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "mm_swarm_realdata_cleantest_2026-11-01.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=str)
print(f"\nwritten: {os.path.join(OUT_DIR, 'mm_swarm_realdata_cleantest_2026-11-01.json')}")
