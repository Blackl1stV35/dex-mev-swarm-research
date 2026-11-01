"""Exploratory search ONLY (per the attached research-design PDF's own gating: this is pre-Phase-3,
a sanity check, not a validated predictive study). No point-in-time audit trail, no walk-forward
split, no model, no trading claim. Scope: one specific protocol's smart contract (Uniswap v3
USDC/WETH 0.05% pool, 0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640) versus real XAUUSD.

Real data only, no synthetic fallback (the PDF's own integrity rule, honored even at exploratory
scope): real broker-sourced XAUUSD H1 (MT5, not the GC=F futures proxy the PDF flags as a notebook
error), real Uniswap v3 on-chain swap data, both already fetched and verified in this project
family -- no new fetch.
"""
import json
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

XAU_PATH = r"D:\xauusd_system\research\afml_multiasset\data\XAUUSD_H1.npz"
UNI_PATH = r"D:\market-dynamics-research\data\uniswap_v3_lp\USDC_WETH_005"
OUT_DIR = r"D:\dex-mev-swarm-research\results"

print("Loading real XAUUSD H1 data (MT5 broker source, not GC=F)...")
xz = np.load(XAU_PATH)
xt, xc = xz["t"].astype(np.int64), xz["c"].astype(float)
xday = pd.to_datetime(xt, unit="s").floor("D")
xau = pd.DataFrame({"date": xday, "close": xc}).groupby("date")["close"].last()
print(f"  XAUUSD: {len(xau)} daily closes, {xau.index.min().date()} to {xau.index.max().date()}")

print("Loading real Uniswap v3 USDC/WETH 0.05% swap data (contract 0x88e6...5640)...")
ts = np.load(os.path.join(UNI_PATH, "ts.npy"))
sqrtp = np.load(os.path.join(UNI_PATH, "sqrtp.npy"))
amount1 = np.load(os.path.join(UNI_PATH, "amount1.npy"))
price = 1e12 / (sqrtp ** 2)
assert 500 < price[0] < 10000, f"price sanity check failed: {price[0]}"
vol_usd = np.abs(amount1) * price
uni_df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").floor("D"), "price": price, "vol_usd": vol_usd})
g = uni_df.groupby("date")
uni_daily = pd.DataFrame({
    "swap_count": g.size(),
    "volume_usd": g["vol_usd"].sum(),
    "last_price": g["price"].last(),
})
print(f"  Uniswap pool: {len(uni_daily)} trading days, {uni_daily.index.min().date()} to {uni_daily.index.max().date()}")

# --- align on the real overlapping calendar, no synthetic fill ---
merged = pd.DataFrame({"xau_close": xau}).join(uni_daily, how="inner").sort_index()
merged["xau_ret"] = np.log(merged["xau_close"]).diff()
merged["xau_absret"] = merged["xau_ret"].abs()
merged["uni_ret"] = np.log(merged["last_price"]).diff()
merged["uni_absret"] = merged["uni_ret"].abs()
merged = merged.dropna()
print(f"\nReal overlapping trading days (both series present, no imputation): {len(merged)}, "
      f"{merged.index.min().date()} to {merged.index.max().date()}")

# --- exploratory correlations (contemporaneous, descriptive only -- no causal or predictive claim) ---
corr_absret = merged["xau_absret"].corr(merged["uni_absret"])
corr_ret = merged["xau_ret"].corr(merged["uni_ret"])
corr_vol_activity = merged["xau_absret"].corr(np.log(merged["volume_usd"]))
corr_swapcount = merged["xau_absret"].corr(np.log(merged["swap_count"]))

print("\n=== Exploratory contemporaneous correlations (descriptive only) ===")
print(f"  XAUUSD |return| vs Uniswap pool |return| (volatility co-movement): {corr_absret:.4f}")
print(f"  XAUUSD return vs Uniswap pool return (directional co-movement):    {corr_ret:.4f}")
print(f"  XAUUSD |return| vs log(Uniswap daily USD volume):                 {corr_vol_activity:.4f}")
print(f"  XAUUSD |return| vs log(Uniswap daily swap count):                 {corr_swapcount:.4f}")

out = dict(n_days=int(len(merged)), start=str(merged.index.min().date()), end=str(merged.index.max().date()),
           corr_abs_return_vs_pool_abs_return=float(corr_absret),
           corr_return_vs_pool_return=float(corr_ret),
           corr_xau_absret_vs_log_uni_volume=float(corr_vol_activity),
           corr_xau_absret_vs_log_uni_swapcount=float(corr_swapcount),
           note="exploratory contemporaneous correlation only; no lag structure, no point-in-time "
                "audit, no validation split -- not a predictive or tradeable claim")
with open(os.path.join(OUT_DIR, "exploratory_xauusd_uniswap_2026-11-02.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)

# --- chart ---
fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True, gridspec_kw={"height_ratios": [1.3, 1, 1]})

ax = axes[0]
ax.plot(merged.index, merged["xau_close"], color="#b8860b", lw=1.2, label="XAUUSD daily close (real, MT5 broker)")
ax.set_ylabel("XAUUSD (USD/oz)")
ax.set_title("Exploratory: XAUUSD vs. Uniswap v3 USDC/WETH 0.05% pool activity (real data, both series)")
ax.legend(fontsize=8, loc="upper left")
ax.grid(alpha=0.3)

ax = axes[1]
ax.plot(merged.index, merged["volume_usd"], color="#2b5c8a", lw=0.9)
ax.set_yscale("log")
ax.set_ylabel("Uniswap pool\ndaily volume (USD, log)")
ax.grid(alpha=0.3, which="both")

ax = axes[2]
ax.plot(merged.index, merged["xau_absret"].rolling(14).mean(), color="#b8860b", lw=1.2,
        label="XAUUSD |return|, 14d avg")
ax2 = ax.twinx()
ax2.plot(merged.index, merged["uni_absret"].rolling(14).mean(), color="#2b5c8a", lw=1.0, ls="--",
         label="Uniswap pool |return|, 14d avg")
ax.set_ylabel("XAUUSD |return|", color="#b8860b")
ax2.set_ylabel("Uniswap pool |return|", color="#2b5c8a")
ax.set_xlabel("Date")
lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc="upper left")
ax.grid(alpha=0.3)
ax.text(0.01, -0.28, f"Contemporaneous correlation, |returns|: {corr_absret:.3f}  |  "
                      f"returns: {corr_ret:.3f}  |  n = {len(merged)} overlapping real trading days "
                      f"({merged.index.min().date()} to {merged.index.max().date()})",
        transform=ax.transAxes, fontsize=8.5)

fig.tight_layout()
chart_path = os.path.join(OUT_DIR, "exploratory_xauusd_uniswap_2026-11-02.png")
fig.savefig(chart_path, dpi=130)
print(f"\nwritten: {chart_path}")
