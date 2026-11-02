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
NAV_SERIES_JSON = os.path.join(HERE, "nav_series.json")
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

    # full series, for the interactive client-side chart -- small (one row per ~10 min poll),
    # safe to ship whole rather than paginating.
    series = df[["ts_utc", "price_usd_per_weth", "nav", "hodl_5050", "hodl_weth", "cum_fees_usd"]].to_dict(orient="records")
    with open(NAV_SERIES_JSON, "w", encoding="utf-8") as fh:
        json.dump(series, fh)

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
    html = rf"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Option B paper trade</title>
<style>
:root {{
  --bg: #0f1115; --panel: #171a21; --ink: #e6e6e6; --muted: #9aa0a8; --grid: #2a2e37;
  --nav: #5b9bd5; --h5050: #e0a458; --hweth: #7ab06c; --fees: #b07ad6; --warn-bg: #3a2a0f; --warn-bd: #8a5a1a;
}}
body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem;
       background: var(--bg); color: var(--ink); }}
h1 {{ font-size: 1.3rem; }}
.warn {{ background: var(--warn-bg); border: 1px solid var(--warn-bd); padding: 0.6rem 1rem; border-radius: 6px; margin-bottom: 1rem; }}
.panel {{ background: var(--panel); border-radius: 8px; padding: 1rem; margin-top: 1rem; }}
.panel h2 {{ font-size: 0.95rem; color: var(--muted); margin: 0 0 0.6rem 0; font-weight: 600; }}
.chart-box {{ position: relative; height: 260px; width: 100%; }}
.chart-box.short {{ height: 180px; }}
canvas {{ max-width: 100%; display: block; touch-action: pan-y; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 0.9rem; font-size: 0.8rem; color: var(--ink); margin-bottom: 0.5rem; }}
.legend span {{ display: inline-flex; align-items: center; gap: 0.35rem; cursor: pointer; user-select: none; }}
.legend .swatch {{ width: 14px; height: 0; border-top-width: 2px; border-top-style: solid; display: inline-block; }}
.legend .off {{ opacity: 0.35; }}
.tooltip {{ position: absolute; background: #20242c; border: 1px solid var(--grid); border-radius: 6px;
           padding: 0.4rem 0.6rem; font-size: 0.78rem; pointer-events: none; white-space: nowrap;
           transform: translate(-50%, -110%); display: none; z-index: 5; font-variant-numeric: tabular-nums; }}
.tooltip .row {{ display: flex; gap: 0.5rem; justify-content: space-between; }}
.jserr {{ color: #e07a7a; font-size: 0.85rem; white-space: pre-wrap; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
td, th {{ border: 1px solid #333; padding: 0.4rem 0.7rem; text-align: left; font-variant-numeric: tabular-nums; }}
.muted {{ color: var(--muted); font-size: 0.85rem; }}
a {{ color: var(--nav); }}
</style></head><body>
<h1>Option B -- Uniswap v3 USDC/WETH 0.05% paper trade</h1>
<div class="warn"><b>PAPER TRADE ONLY.</b> No real funds, no on-chain position actually opened.
Simulated $1 full-range LP position tracked forward from the first poll, using the real live
pool's own on-chain state (price, liquidity, exact feeGrowthGlobal fee accounting).</div>

<div class="panel">
  <h2>NAV, from $1 entry</h2>
  <div id="navLegend" class="legend"></div>
  <div class="chart-box"><canvas id="navChart"></canvas><div id="navTooltip" class="tooltip"></div></div>
</div>
<div class="panel">
  <h2>Cumulative fees earned (USD, real feeGrowthGlobal accounting)</h2>
  <div class="chart-box short"><canvas id="feeChart"></canvas><div id="feeTooltip" class="tooltip"></div></div>
</div>
<div id="chartErr" class="jserr"></div>
<p><a href="nav_chart.png">Static image (for sharing)</a> | <a href="nav_series.json">Raw series JSON</a></p>

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

<script>
// Dependency-free: no CDN, no external library, no Intl/toLocaleString anywhere in this
// file. A real iOS device threw "The string did not match the expected pattern" even
// after every Intl call of MY OWN was removed -- the remaining suspect was Chart.js's own
// internal tick/legend formatting, which likely still touches Intl somewhere. Removing the
// library outright removes that whole class of risk, not just the part I could see.

function toDate(s) {{
  // Safari/WebKit's Date parser rejects ISO strings with >3 fractional-second digits
  // (Python's isoformat() emits microseconds); Chrome tolerates it. Truncate first.
  return new Date(s.replace(/\.(\d{{3}})\d*/, '.$1'));
}}
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(d) {{
  const h = d.getHours(), hh = String(((h + 11) % 12) + 1).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return MONTHS[d.getMonth()] + ' ' + d.getDate() + ', ' + hh + ':' + mm + ' ' + (h < 12 ? 'AM' : 'PM');
}}
function niceTicks(lo, hi, n) {{
  if (lo === hi) {{ lo -= 1; hi += 1; }}
  const span = hi - lo, rough = span / n;
  const mag = Math.pow(10, Math.floor(Math.log(rough) / Math.LN10));
  const norm = rough / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(lo / step) * step;
  const out = [];
  for (let v = start; v <= hi + step * 1e-9; v += step) out.push(v);
  return out;
}}

// series: [{{label, color, dash:[..]|null, points:boolean, values:number[]}}], shared x labels.
function drawChart(canvas, tooltipEl, legendEl, labels, series, yDecimals) {{
  const box = canvas.parentElement;
  const dpr = window.devicePixelRatio || 1;
  const cssW = box.clientWidth, cssH = box.clientHeight;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const css = getComputedStyle(document.documentElement);
  const gridColor = css.getPropertyValue('--grid').trim();
  const mutedColor = css.getPropertyValue('--muted').trim();

  const active = series.filter(s => s.enabled !== false);
  const allVals = active.flatMap(s => s.values).filter(v => Number.isFinite(v));
  const vMin = Math.min(...allVals), vMax = Math.max(...allVals);
  const pad = (vMax - vMin) * 0.1 || Math.abs(vMax) * 0.01 || 1;
  const yLo = vMin - pad, yHi = vMax + pad;
  const yTicks = niceTicks(yLo, yHi, 5);

  const left = 58, right = 10, top = 10, bottom = 26;
  const plotW = cssW - left - right, plotH = cssH - top - bottom;
  const n = labels.length;
  const xAt = i => left + (n <= 1 ? plotW / 2 : (plotW * i) / (n - 1));
  const yAt = v => top + plotH - ((v - yLo) / (yHi - yLo)) * plotH;

  ctx.strokeStyle = gridColor; ctx.lineWidth = 1; ctx.font = '11px -apple-system, sans-serif';
  ctx.fillStyle = mutedColor; ctx.textBaseline = 'middle';
  yTicks.forEach(v => {{
    const y = yAt(v);
    ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + plotW, y); ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(v.toFixed(yDecimals), left - 8, y);
  }});
  const xTickEvery = Math.max(1, Math.ceil(n / 4));
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  for (let i = 0; i < n; i += xTickEvery) ctx.fillText(labels[i], xAt(i), top + plotH + 8);

  active.forEach(s => {{
    ctx.beginPath();
    ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    ctx.setLineDash(s.dash || []);
    s.values.forEach((v, i) => {{
      const x = xAt(i), y = yAt(v);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }});
    ctx.stroke();
    ctx.setLineDash([]);
    if (s.points) {{
      ctx.fillStyle = s.color;
      s.values.forEach((v, i) => {{
        ctx.beginPath(); ctx.arc(xAt(i), yAt(v), 2.5, 0, 7); ctx.fill();
      }});
    }}
  }});

  if (legendEl && !legendEl.dataset.built) {{
    legendEl.dataset.built = '1';
    legendEl.innerHTML = '';
    series.forEach((s, idx) => {{
      const el = document.createElement('span');
      el.innerHTML = '<span class="swatch" style="border-color:' + s.color + (s.dash ? ';border-top-style:dashed' : '') + '"></span>' + s.label;
      el.addEventListener('click', () => {{
        series[idx].enabled = series[idx].enabled === false ? true : false;
        el.classList.toggle('off', series[idx].enabled === false);
        drawChart(canvas, tooltipEl, legendEl, labels, series, yDecimals);
      }});
      legendEl.appendChild(el);
    }});
  }}

  if (tooltipEl && !canvas.dataset.hoverBound) {{
    canvas.dataset.hoverBound = '1';
    const showAt = (clientX, clientY) => {{
      const rect = canvas.getBoundingClientRect();
      const x = clientX - rect.left;
      let idx = Math.round(((x - left) / plotW) * (n - 1));
      idx = Math.max(0, Math.min(n - 1, idx));
      const rows = active.map(s => '<div class="row"><span style="color:' + s.color + '">' + s.label + '</span><span>' + s.values[idx].toFixed(yDecimals) + '</span></div>').join('');
      tooltipEl.innerHTML = '<div>' + labels[idx] + '</div>' + rows;
      tooltipEl.style.display = 'block';
      tooltipEl.style.left = xAt(idx) + 'px';
      tooltipEl.style.top = Math.min(...active.map(s => yAt(s.values[idx]))) + 'px';
    }};
    canvas.addEventListener('mousemove', e => showAt(e.clientX, e.clientY));
    canvas.addEventListener('mouseleave', () => {{ tooltipEl.style.display = 'none'; }});
    canvas.addEventListener('touchstart', e => {{ showAt(e.touches[0].clientX, e.touches[0].clientY); }}, {{ passive: true }});
    canvas.addEventListener('touchmove', e => {{ showAt(e.touches[0].clientX, e.touches[0].clientY); }}, {{ passive: true }});
  }}
}}

async function render() {{
  const rows = await (await fetch('nav_series.json?t=' + Date.now())).json();
  const labels = rows.map(r => fmtDate(toDate(r.ts_utc)));
  const css = getComputedStyle(document.documentElement);
  const colors = {{
    nav: css.getPropertyValue('--nav').trim(), h5050: css.getPropertyValue('--h5050').trim(),
    hweth: css.getPropertyValue('--hweth').trim(), fees: css.getPropertyValue('--fees').trim(),
  }};

  const navCanvas = document.getElementById('navChart'), navTooltip = document.getElementById('navTooltip'), navLegend = document.getElementById('navLegend');
  const navSeries = [
    {{ label: 'Paper LP NAV', color: colors.nav, points: true, values: rows.map(r => r.nav) }},
    {{ label: 'HODL 50/50', color: colors.h5050, dash: [6,3], values: rows.map(r => r.hodl_5050) }},
    {{ label: 'HODL 100% WETH', color: colors.hweth, dash: [2,2], values: rows.map(r => r.hodl_weth) }},
  ];
  const feeCanvas = document.getElementById('feeChart'), feeTooltip = document.getElementById('feeTooltip');
  const feeSeries = [{{ label: 'Cumulative fees (USD)', color: colors.fees, points: true, values: rows.map(r => r.cum_fees_usd) }}];

  const redrawNav = () => drawChart(navCanvas, navTooltip, navLegend, labels, navSeries, 4);
  const redrawFee = () => drawChart(feeCanvas, feeTooltip, null, labels, feeSeries, 8);
  redrawNav(); redrawFee();
  window.addEventListener('resize', () => {{ redrawNav(); redrawFee(); }});
}}
render().catch(e => {{ document.getElementById('chartErr').textContent = 'Chart render error: ' + e.message; }});
</script>
</body></html>"""
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    poll_and_append()
    recompute_nav()
