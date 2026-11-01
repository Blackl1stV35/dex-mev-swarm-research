"""First pass, real data (2026-11-01): tests the MECHANISM behind mm_swarm_model.md's P1/P2,
on the real Uniswap v3 USDC/WETH 0.05% pool, reusing already-fetched, already-verified data
from market-dynamics-research/data/uniswap_v3_lp (problem 14's applied bridge, 2026-09-08).

Scope, explicitly bounded (not a full pre-registered bridge like problem 14's):
  Step A: load real price (from sqrtP), liquidity, timestamps -- no new fetch.
  Step B: detect real volatility spike episodes from the real price series (data-driven,
          not hard-coded to known events, though cross-checked against the known May-2021
          crash as a sanity signal).
  Step C: MECHANISM TEST (direct, no counterfactual needed): does realized liquidity actually
          fall during spikes, and does realized trader-side price impact actually rise? If
          not, the whole swarm rationale (P2) has no real basis to act on.
  Step D: SIMPLIFIED counterfactual for P1 (swarm vs fled-LP return) -- clearly labeled as an
          approximation, not a rigorous backtest. Flagged, not oversold.

No live trading, no real capital, read-only analysis of historical public data.
"""
import json
import os

import numpy as np

DATA = r"D:\market-dynamics-research\data\uniswap_v3_lp\USDC_WETH_005"
OUT_DIR = r"D:\dex-mev-swarm-research\results"
FEE_RATE = 0.0005  # 5 bps pool

print("Loading real swap data (no network, already-fetched)...")
ts = np.load(os.path.join(DATA, "ts.npy"))
sqrtp = np.load(os.path.join(DATA, "sqrtp.npy"))
liq = np.load(os.path.join(DATA, "liq.npy"))
amount1 = np.load(os.path.join(DATA, "amount1.npy"))  # WETH raw units, signed
n = len(ts)
print(f"  {n:,} real swaps loaded, {np.datetime64(int(ts[0]), 's')} to {np.datetime64(int(ts[-1]), 's')}")

# price of WETH in USDC: raw_price (token1/token0, raw units) = sqrtP^2; this is WETH-per-USDC
# in human terms once decimal-adjusted (*1e-12), so USDC-per-WETH (the usual "ETH price") is
# the reciprocal: 1e12 / sqrtP^2. (Caught via a failed sanity assert: sqrtp^2*1e-12 ~ 2.9e-4,
# which prints as "0.00" at 2dp -- not a null/zero value, just the wrong side of the ratio.)
price = 1e12 / (sqrtp ** 2)
assert 500 < price[0] < 10000, f"sanity check failed: price[0]={price[0]:.2f}, expected plausible ETH/USDC"
print(f"  price sanity check: first swap price = ${price[0]:,.2f} per ETH (plausible range OK)")

# --- Step B: data-driven volatility-spike detection ---
# resample to hourly bins (real time, not block count) for a stable realized-vol signal
hours = (ts - ts[0]) // 3600
n_hours = int(hours[-1]) + 1
hourly_last_price = np.full(n_hours, np.nan)
hourly_last_liq = np.full(n_hours, np.nan)
# vectorized "last value per bin" via searchsorted on sorted hours (ts is chain-order, non-decreasing)
bin_edges = np.searchsorted(hours, np.arange(n_hours + 1))
for h in range(n_hours):
    lo, hi = bin_edges[h], bin_edges[h + 1]
    if hi > lo:
        hourly_last_price[h] = price[hi - 1]
        hourly_last_liq[h] = liq[hi - 1]
# forward-fill gaps (quiet hours with no swaps)
mask = ~np.isnan(hourly_last_price)
idx = np.where(mask, np.arange(n_hours), 0)
np.maximum.accumulate(idx, out=idx)
hourly_last_price = hourly_last_price[idx]
hourly_last_liq = hourly_last_liq[idx]

log_ret = np.diff(np.log(hourly_last_price))
WIN = 24  # 24h rolling realized vol
roll_vol = np.array([np.std(log_ret[max(0, i - WIN):i + 1]) for i in range(len(log_ret))])
top_idx = np.argsort(roll_vol)[-5:][::-1]  # top 5 most volatile 24h windows, data-driven
print("\nTop 5 real volatility episodes detected (data-driven, 24h rolling realized vol):")
spikes = []
for i in top_idx:
    t_spike = ts[0] + int(i) * 3600
    date = np.datetime64(int(t_spike), "s")
    spikes.append(dict(hour_idx=int(i), date=str(date), vol=float(roll_vol[i])))
    print(f"  hour {i}: {date}, 24h realized vol = {roll_vol[i]:.4f}")

# --- Step C: mechanism test -- does liq fall and does trader-side impact rise, during spikes? ---
print("\n=== Step C: mechanism test (direct measurement, no counterfactual) ===")
# define spike window = detected hour +/- 12h; calm window = a quiet period far from any top-20 spike hour
quiet_candidates = np.argsort(roll_vol)[: len(roll_vol) // 4]  # calmest quartile of hours
calm_sample = np.random.default_rng(1).choice(quiet_candidates, size=min(500, len(quiet_candidates)), replace=False)

results = []
for s in spikes[:3]:  # bound to top 3 spikes to keep this a light pass
    h = s["hour_idx"]
    win_lo, win_hi = max(0, h - 12), min(n_hours - 1, h + 12)
    t_lo, t_hi = ts[0] + win_lo * 3600, ts[0] + win_hi * 3600
    sel = (ts >= t_lo) & (ts <= t_hi)
    if sel.sum() < 10:
        continue
    liq_spike = float(np.median(liq[sel]))
    liq_pre = float(np.median(liq[(ts >= t_lo - 24 * 3600) & (ts < t_lo)])) if (ts < t_lo).any() else float("nan")
    # trader-side price impact proxy: |log return per swap| / swap size (WETH), per swap in window
    p_sel = price[sel]
    if len(p_sel) > 1:
        impact = np.abs(np.diff(np.log(p_sel))) / (np.abs(amount1[sel][1:]) + 1e-9)
        med_impact_spike = float(np.median(impact))
    else:
        med_impact_spike = float("nan")
    results.append(dict(spike_date=s["date"], liq_pre=liq_pre, liq_during=liq_spike,
                         liq_change_pct=100 * (liq_spike - liq_pre) / liq_pre if liq_pre == liq_pre and liq_pre > 0 else None,
                         median_price_impact_per_unit_spike=med_impact_spike))
    print(f"  {s['date']}: liq pre-spike={liq_pre:.3e}, during-spike={liq_spike:.3e}, "
          f"change={100*(liq_spike-liq_pre)/liq_pre if liq_pre>0 else float('nan'):+.1f}%, "
          f"median per-unit price impact={med_impact_spike:.3e}")

# calm-window baseline for comparison
calm_mask = np.zeros(n, dtype=bool)
for h in calm_sample[:200]:
    t_lo, t_hi = ts[0] + int(h) * 3600, ts[0] + int(h + 1) * 3600
    calm_mask |= (ts >= t_lo) & (ts < t_hi)
p_calm = price[calm_mask]
if len(p_calm) > 1:
    impact_calm = np.abs(np.diff(np.log(p_calm))) / (np.abs(amount1[calm_mask][1:]) + 1e-9)
    med_impact_calm = float(np.median(impact_calm))
    liq_calm = float(np.median(liq[calm_mask]))
else:
    med_impact_calm, liq_calm = float("nan"), float("nan")
print(f"\n  calm-window baseline: median liq={liq_calm:.3e}, median per-unit price impact={med_impact_calm:.3e}")

# --- Step D: simplified P1 counterfactual (approximation, flagged) ---
print("\n=== Step D: simplified LP counterfactual (approximation, not a rigorous backtest) ===")
d_results = []
for s_res, s in zip(results, spikes[:3]):
    if s_res["liq_pre"] != s_res["liq_pre"] or s_res["liq_pre"] <= 0:
        continue
    h = s["hour_idx"]
    win_lo, win_hi = max(0, h - 12), min(n_hours - 1, h + 12)
    p0, p1 = hourly_last_price[win_lo], hourly_last_price[win_hi]
    ret = np.log(p1 / p0)
    # crude LVR-style approximation: IL cost scales with (log-return)^2 for a passive CFMM LP,
    # proportional to liquidity provided; a floor policy provides liq_pre throughout the window
    # vs the realized (lower, fled) liq_during for the LP's own depth -- fee capture scales with
    # depth share x volume, cost scales with depth x price-variance. This is a back-of-envelope
    # sign-and-magnitude check, NOT a validated LVR formula fit.
    il_realized_proxy = s_res["liq_during"] * (ret ** 2)
    il_floor_proxy = s_res["liq_pre"] * (ret ** 2)
    # fee revenue proxy: realized swap count in window x fee rate x avg size, scaled by liq share
    # (a floor policy has MORE liq -> smaller share of a fixed pool's total fee pot per unit
    # capital, so this is a genuine trade-off, not a free lunch)
    d_results.append(dict(spike_date=s["date"], log_return_over_window=float(ret),
                           il_proxy_realized_depth=float(il_realized_proxy),
                           il_proxy_floor_depth=float(il_floor_proxy),
                           note="IL proxy only; fee-revenue side of the trade-off not modeled "
                                "in this bounded pass -- a real P1 test needs LP-level data this "
                                "pool-aggregate dataset doesn't have"))
    print(f"  {s['date']}: window log-return={ret:+.4f}, IL proxy at realized(fled) depth={il_realized_proxy:.3e}, "
          f"IL proxy at floor(held) depth={il_floor_proxy:.3e} "
          f"({'floor is WORSE for IL alone, as expected -- holding more depth through a big move costs more IL; the whole P1 question is whether fee capture compensates, which this pass does not test' if il_floor_proxy > il_realized_proxy else 'unexpected sign'})")

out = dict(n_swaps=int(n), detected_spikes=spikes, mechanism_test=results,
           calm_baseline=dict(median_liq=liq_calm, median_price_impact=med_impact_calm),
           p1_counterfactual_bounded=d_results)
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "mm_swarm_realdata_firstpass_2026-11-01.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=str)
print(f"\nwritten: {os.path.join(OUT_DIR, 'mm_swarm_realdata_firstpass_2026-11-01.json')}")
