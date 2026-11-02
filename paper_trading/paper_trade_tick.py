#!/usr/bin/env python
"""Option B paper-trading tick: one real on-chain poll + NAV recompute. No funds move.

Run standalone (idempotent, safe to re-run): polls the REAL, live Uniswap v3 USDC/WETH 0.05%
pool (0x88e6a0c2dDD26FEEb64F039a2c41296FcB3f5640) over a public JSON-RPC endpoint, appends one
row to pool_state_log.csv, then recomputes the paper position's NAV from the full log and
rewrites nav_summary.json + nav_chart.png.

FEE ACCOUNTING -- more exact than the historical backtest (research/mm_backtest.py), which
approximated fee income from per-swap volume. This script instead reads the pool's own
feeGrowthGlobal0X128 / feeGrowthGlobal1X128 accumulators directly -- the same primitive the
real Uniswap v3 contract uses internally to compute any LP's actual claimable fees. For a
full-range position (always in-range), fee earned over an interval for liquidity l0 is exactly
  fee_token_raw = l0 * delta(feeGrowthGlobalX128) / 2**128
with no approximation.

POSITION MODEL: identical to research/mm_backtest.py -- a full-range (v2-equivalent) position
sized to be worth exactly $1 at the first poll (entry), held constant (never withdrawn, never
rebalanced). IL via the standard sqrt(P_t/P_0) identity.
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from datetime import datetime, timezone

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RPC = "https://ethereum-rpc.publicnode.com"
POOL = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_CSV = os.path.join(HERE, "pool_state_log.csv")
NAV_JSON = os.path.join(HERE, "nav_summary.json")
CHART_PNG = os.path.join(HERE, "nav_chart.png")

SELECTORS = {
    "slot0": "0x3850c7bd",
    "liquidity": "0x1a686502",
    "feeGrowthGlobal0X128": "0xf3058399",
    "feeGrowthGlobal1X128": "0x46141319",
}


HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (paper-trade-poller/1.0)"}


def eth_call(data: str) -> str:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                           "params": [{"to": POOL, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(RPC, data=payload, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        out = json.loads(resp.read())
    if "error" in out:
        raise RuntimeError(f"RPC error for {data}: {out['error']}")
    return out["result"]


def eth_block_number() -> int:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}).encode()
    req = urllib.request.Request(RPC, data=payload, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        out = json.loads(resp.read())
    return int(out["result"], 16)


def poll_and_append() -> None:
    block = eth_block_number()
    slot0 = eth_call(SELECTORS["slot0"])
    liq_hex = eth_call(SELECTORS["liquidity"])
    fg0_hex = eth_call(SELECTORS["feeGrowthGlobal0X128"])
    fg1_hex = eth_call(SELECTORS["feeGrowthGlobal1X128"])

    # slot0() returns a static tuple: each field in its own 32-byte word.
    # word0 = sqrtPriceX96 (uint160, right-aligned); word1 = tick (int24, right-aligned, two's complement).
    raw = slot0[2:]  # strip 0x
    word0 = int(raw[0:64], 16)
    sqrt_price_x96 = word0  # uint160 fits in 64 hex chars with leading zero padding
    word1 = int(raw[64:128], 16)
    tick = word1 - (1 << 256) if word1 >= (1 << 255) else word1  # sign-extend int24-in-256

    liquidity = int(liq_hex, 16)
    fee_growth_0 = int(fg0_hex, 16)
    fee_growth_1 = int(fg1_hex, 16)

    sqrtp_scaled = sqrt_price_x96 / (2 ** 96)  # matches this project's sqrtp.npy convention
    price_usd_per_weth = 1e12 / (sqrtp_scaled ** 2)
    assert 200 < price_usd_per_weth < 50000, f"price sanity check failed: {price_usd_per_weth}"

    row = dict(
        ts_utc=datetime.now(timezone.utc).isoformat(),
        block=block,
        sqrtp_scaled=sqrtp_scaled,
        price_usd_per_weth=price_usd_per_weth,
        liquidity=liquidity,
        tick=tick,
        fee_growth_global_0_x128=fee_growth_0,
        fee_growth_global_1_x128=fee_growth_1,
    )

    is_new = not os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            w.writeheader()
        w.writerow(row)
    print(f"polled block {block}: price=${price_usd_per_weth:,.2f}, liquidity={liquidity}")


def recompute_nav() -> None:
    # feeGrowthGlobalX128 values are huge Q128 fixed-point integers that overflow int64/float64
    # precision -- read them as true Python ints (arbitrary precision) via converters, not pandas'
    # default numeric inference, or the subtraction below silently loses precision or errors.
    df = pd.read_csv(LOG_CSV, converters={
        "fee_growth_global_0_x128": int,
        "fee_growth_global_1_x128": int,
        "liquidity": int,
    })
    if len(df) < 1:
        return

    sqrtp0 = df["sqrtp_scaled"].iloc[0]
    l0 = sqrtp0 * 5e5  # calibrated to be worth exactly $1 at entry (same identity as mm_backtest.py)

    price0 = df["price_usd_per_weth"].iloc[0]
    df["r_t"] = df["price_usd_per_weth"] / price0
    df["position_value_ex_fees"] = np.sqrt(df["r_t"])  # full-range IL identity

    fg0_0 = df["fee_growth_global_0_x128"].iloc[0]
    fg1_0 = df["fee_growth_global_1_x128"].iloc[0]
    # fee owed to our l0, in raw token units, since entry (monotonic counters -- safe even if a
    # poll is missed, since this is cumulative-since-entry, not incremental).
    fee0_raw = l0 * (df["fee_growth_global_0_x128"] - fg0_0) / (2 ** 128)
    fee1_raw = l0 * (df["fee_growth_global_1_x128"] - fg1_0) / (2 ** 128)
    fee0_usd = fee0_raw / 1e6                                   # USDC, 6 decimals
    fee1_usd = (fee1_raw / 1e18) * df["price_usd_per_weth"]     # WETH, 18 decimals
    df["cum_fees_usd"] = fee0_usd + fee1_usd

    df["nav"] = df["position_value_ex_fees"] + df["cum_fees_usd"]
    df["hodl_5050"] = 0.5 + 0.5 * df["r_t"]
    df["hodl_weth"] = df["r_t"]

    last = df.iloc[-1]
    summary = dict(
        entry_ts_utc=df["ts_utc"].iloc[0],
        latest_ts_utc=last["ts_utc"],
        n_polls=len(df),
        entry_price_usd=float(price0),
        latest_price_usd=float(last["price_usd_per_weth"]),
        nav=float(last["nav"]),
        cum_fees_usd=float(last["cum_fees_usd"]),
        hodl_5050=float(last["hodl_5050"]),
        hodl_weth=float(last["hodl_weth"]),
        note="PAPER TRADE ONLY -- no real funds, no on-chain position actually opened. Polls the "
             "real live pool's own feeGrowthGlobal accumulators for exact (non-approximated) fee "
             "accounting on a simulated $1 full-range position entered at the first poll.",
    )
    with open(NAV_JSON, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    if len(df) >= 2:
        t = pd.to_datetime(df["ts_utc"])
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
        ax1.plot(t, df["nav"], color="#2b5c8a", lw=1.8, marker="o", ms=3, label="Paper LP NAV")
        ax1.plot(t, df["hodl_5050"], color="#c9742c", lw=1.2, ls="--", label="HODL 50/50")
        ax1.plot(t, df["hodl_weth"], color="#4f8a3b", lw=1.0, ls=":", label="HODL 100% WETH")
        ax1.axhline(1.0, color="#999999", lw=0.8)
        ax1.set_ylabel("NAV, from $1")
        ax1.set_title("Option B PAPER TRADE (live, no real funds) -- Uniswap v3 USDC/WETH 0.05%")
        ax1.legend(fontsize=8, loc="best")
        ax1.grid(alpha=0.3)
        ax2.plot(t, df["cum_fees_usd"], color="#8c4fa0", lw=1.6, marker="o", ms=3)
        ax2.set_ylabel("Cum. fees (USD, real\nfeeGrowthGlobal accounting)")
        ax2.set_xlabel("UTC time")
        ax2.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(CHART_PNG, dpi=130)
        plt.close(fig)

    print(f"NAV: ${last['nav']:.6f}  (fees ${last['cum_fees_usd']:.6f})  n_polls={len(df)}")
    write_index_html(summary)


def write_index_html(summary: dict) -> None:
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="300">
<title>Option B paper trade</title>
<style>
body {{ font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem;
       background: #0f1115; color: #e6e6e6; }}
h1 {{ font-size: 1.3rem; }}
.warn {{ background: #4a2f0a; border: 1px solid #8a5a1a; padding: 0.6rem 1rem; border-radius: 6px; margin-bottom: 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
td, th {{ border: 1px solid #333; padding: 0.4rem 0.7rem; text-align: left; font-variant-numeric: tabular-nums; }}
img {{ max-width: 100%; border-radius: 6px; margin-top: 1rem; }}
.muted {{ color: #999; font-size: 0.85rem; }}
</style></head><body>
<h1>Option B -- Uniswap v3 USDC/WETH 0.05% paper trade</h1>
<div class="warn"><b>PAPER TRADE ONLY.</b> No real funds, no on-chain position actually opened.
Simulated $1 full-range LP position tracked forward from the first poll, using the real live
pool's own on-chain state (price, liquidity, exact feeGrowthGlobal fee accounting).</div>
<p><a href="nav_chart.png">Quick view (chart image only)</a></p>
<img src="nav_chart.png" alt="NAV chart">
<table>
<tr><th>Entry time (UTC)</th><td>{summary['entry_ts_utc']}</td></tr>
<tr><th>Latest poll (UTC)</th><td>{summary['latest_ts_utc']}</td></tr>
<tr><th># polls</th><td>{summary['n_polls']}</td></tr>
<tr><th>Entry price</th><td>${summary['entry_price_usd']:,.2f}</td></tr>
<tr><th>Latest price</th><td>${summary['latest_price_usd']:,.2f}</td></tr>
<tr><th>Paper LP NAV</th><td>${summary['nav']:.6f}</td></tr>
<tr><th>Cumulative fees</th><td>${summary['cum_fees_usd']:.6f}</td></tr>
<tr><th>HODL 50/50</th><td>${summary['hodl_5050']:.6f}</td></tr>
<tr><th>HODL 100% WETH</th><td>${summary['hodl_weth']:.6f}</td></tr>
</table>
<p class="muted">Updates every ~10 min via a Windows Scheduled Task (DexMevSwarm_PaperTrade_OptionB).
Raw log: <a href="pool_state_log.csv">pool_state_log.csv</a> |
JSON: <a href="nav_summary.json">nav_summary.json</a></p>
</body></html>"""
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    poll_and_append()
    recompute_nav()
