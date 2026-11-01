"""Builds the Option B trading strategy document as a PDF, matplotlib PdfPages backend
(same mechanism the project's established document pattern uses -- no external PDF library
needed; checked, Times New Roman is installed, no install required).

Concise, executive-ready content only. Process notes, scope caveats, and methodology
commentary are NOT in this document -- they're in the chat response that accompanies it.
"""
import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

plt.rcParams["font.family"] = "Times New Roman"
plt.rcParams["text.color"] = "black"
plt.rcParams["axes.edgecolor"] = "black"

OUT = r"D:\dex-mev-swarm-research\results\option_b_strategy_document_2026-11-02.pdf"
CHART = r"D:\dex-mev-swarm-research\results\mm_backtest_2026-11-02.png"
PAGE = (8.5, 11)

# ----------------------------------------------------------------------------- real figures
FINAL_NAV = 1.1070597854469142
HODL_5050 = 0.867
HODL_WETH = 0.733
OUTPERF_PP = 24.1
FEE_INCOME = 0.251
MAX_DD_PCT = -49.1
MAX_DD_DATE = "2022-06-18"
PERIOD = "2021-05-05 to 2026-09-08 (5.35 years)"
ETH_START = 3402.73
ETH_END = 2494.52
MEDIAN_TVL = 1_145_064_286

GAS_MINT = 220_000
GAS_EXIT = 180_000
GWEI_TYPICAL = 1.0
GWEI_SPIKE = 5.0
ETH_FOR_GAS = ETH_END


def gas_usd(gas_units, gwei):
    return gas_units * gwei * 1e-9 * ETH_FOR_GAS


ROUND_TRIP_TYPICAL = gas_usd(GAS_MINT + GAS_EXIT, GWEI_TYPICAL)
ROUND_TRIP_SPIKE = gas_usd(GAS_MINT + GAS_EXIT, GWEI_SPIKE)
BREAKEVEN_CAPITAL_1PCT = ROUND_TRIP_SPIKE / 0.01


def new_page(pdf):
    fig = plt.figure(figsize=PAGE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    # escape literal "$" everywhere on this page: matplotlib treats a matched pair of "$"
    # as mathtext delimiters, which silently swallows spacing between two dollar amounts
    # in the same string (caught via the required visual-verification pass, not assumed OK).
    _orig_text = ax.text
    def _safe_text(x, y, s, *a, **kw):
        return _orig_text(x, y, s.replace("$", r"\$"), *a, **kw)
    ax.text = _safe_text
    return fig, ax


def text_block(ax, x, y, s, size=10.5, weight="normal", lh=0.0215, max_width=None):
    import textwrap
    width = max_width or 95
    lines = []
    for para in s.split("\n"):
        if para.strip() == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(para, width=width) or [""])
    for i, line in enumerate(lines):
        ax.text(x, y - i * lh, line, fontsize=size, fontweight=weight, va="top", ha="left")
    return y - len(lines) * lh


with PdfPages(OUT) as pdf:
    # ---------------------------------------------------------------- page 1: cover + exec summary
    fig, ax = new_page(pdf)
    ax.text(0.5, 0.92, "Uniswap v3 Full-Range Liquidity Provision Strategy", fontsize=18,
            weight="bold", ha="center")
    ax.text(0.5, 0.885, "USDC/WETH 0.05% Pool: Trading Strategy Document", fontsize=12.5,
            ha="center", style="italic")
    ax.text(0.5, 0.855, "Prepared 2026-11-02  |  Pending sign-off for live deployment", fontsize=9.5,
            ha="center")
    ax.axhline(0.835, xmin=0.08, xmax=0.92, color="black", lw=0.6)

    y = 0.80
    ax.text(0.08, y, "Executive Summary", fontsize=13, weight="bold")
    y -= 0.03
    y = text_block(ax, 0.08, y, (
        f"This document specifies a passive, full-range liquidity-provision strategy on the "
        f"Uniswap v3 USDC/WETH 0.05% pool. Backtested on the pool's complete real trading "
        f"history, {PERIOD}, the strategy returned {(FINAL_NAV - 1) * 100:+.1f}%, against "
        f"{(HODL_5050 - 1) * 100:+.1f}% for a 50/50 USDC and WETH buy-and-hold benchmark and "
        f"{(HODL_WETH - 1) * 100:+.1f}% for a 100% WETH buy-and-hold benchmark, an outperformance "
        f"of {OUTPERF_PP:+.1f} percentage points over the 50/50 benchmark. Fee income accounted "
        f"for {FEE_INCOME:.3f} of the {FINAL_NAV:.3f} final value per dollar invested."
    ))
    y -= 0.015
    y = text_block(ax, 0.08, y, (
        f"The strategy requires one on-chain transaction to enter and one to exit, and no active "
        f"management between them. At current Ethereum network gas prices, round-trip "
        f"transaction cost is approximately ${ROUND_TRIP_TYPICAL:.2f} under typical conditions "
        f"and approximately ${ROUND_TRIP_SPIKE:.2f} under elevated conditions, making the "
        f"strategy cost-efficient at position sizes above approximately "
        f"${BREAKEVEN_CAPITAL_1PCT:,.0f}."
    ))
    y -= 0.015
    y = text_block(ax, 0.08, y, (
        f"The backtest period includes two real market drawdowns. The strategy's maximum "
        f"drawdown over the period was {MAX_DD_PCT:.1f}%, reached on {MAX_DD_DATE}. A position "
        f"of this kind should be sized as risk capital, with the exit criteria in Section 5 "
        f"applied, not held on the assumption that the historical return repeats."
    ))

    y -= 0.04
    ax.text(0.08, y, "Recommendation", fontsize=13, weight="bold")
    y -= 0.03
    y = text_block(ax, 0.08, y, (
        "Proceed to a small, capital-limited live deployment (Section 4 sizing guidance; "
        "Section 5 exit criteria) only once sign-off is formally given. This document is the "
        "strategy specification for that decision, not an instruction to deploy."
    ))
    pdf.savefig(fig)
    plt.close(fig)

    # ---------------------------------------------------------------- page 2: strategy spec
    fig, ax = new_page(pdf)
    ax.text(0.08, 0.93, "1. Strategy Specification", fontsize=13.5, weight="bold")
    y = 0.885
    y = text_block(ax, 0.08, y, (
        "Position: a single full-range (minimum tick to maximum tick) Uniswap v3 position in "
        "the USDC/WETH 0.05% fee-tier pool, capitalized with a 50/50 value split between USDC "
        "and WETH at entry, held without rebalancing."
    ))
    y -= 0.02
    ax.text(0.08, y, "Valuation (impermanent-loss exposure)", fontsize=11, weight="bold")
    y -= 0.028
    y = text_block(ax, 0.08, y, (
        "Let P_0 be the WETH/USDC price at entry and P_t the price at time t. For a full-range "
        "position, position value relative to entry value is exactly sqrt(P_t / P_0), "
        "independent of position size. This is the standard constant-product impermanent-loss "
        "identity and requires no estimation."
    ))
    y -= 0.03
    ax.text(0.08, y, "Fee income", fontsize=11, weight="bold")
    y -= 0.028
    y = text_block(ax, 0.08, y, (
        "The position's liquidity contribution is fixed at entry. Its share of trading fees at "
        "any time equals its own liquidity divided by the pool's total liquidity at that time, "
        "which varies with other liquidity providers' activity. Fee income accrues "
        "automatically inside the position and compounds into its value; no separate collection "
        "transaction is required to earn it, only to realize it in a wallet."
    ))
    y -= 0.03
    ax.text(0.08, y, "Position sizing at entry", fontsize=11, weight="bold")
    y -= 0.028
    y = text_block(ax, 0.08, y, (
        f"Entry requires swapping a portion of capital to reach a 50/50 USDC and WETH split "
        f"before minting the position. This swap costs the pool's own 0.05% trading fee plus "
        f"negligible price impact at the position sizes under consideration here, given the "
        f"pool's typical depth (median observed total value locked ${MEDIAN_TVL:,.0f} over the "
        f"backtest period)."
    ))
    pdf.savefig(fig)
    plt.close(fig)

    # ---------------------------------------------------------------- page 3: backtest result
    fig, ax = new_page(pdf)
    ax.text(0.08, 0.95, "2. Backtest Result", fontsize=13.5, weight="bold")
    y = 0.90
    y = text_block(ax, 0.08, y, (
        f"Source: complete real swap history of the USDC/WETH 0.05% pool, {PERIOD}, "
        f"11,599,763 swaps. No synthetic or simulated data."
    ))
    img = plt.imread(CHART)
    inset = fig.add_axes([0.10, 0.28, 0.80, 0.58])
    inset.imshow(img)
    inset.axis("off")

    rows = [
        ("Strategy final value (from $1.00)", f"${FINAL_NAV:.3f}  ({(FINAL_NAV - 1) * 100:+.1f}%)"),
        ("50/50 HODL benchmark", f"${HODL_5050:.3f}  ({(HODL_5050 - 1) * 100:+.1f}%)"),
        ("100% WETH HODL benchmark", f"${HODL_WETH:.3f}  ({(HODL_WETH - 1) * 100:+.1f}%)"),
        ("Cumulative fee income (from $1.00)", f"${FEE_INCOME:.3f}"),
        ("Maximum drawdown", f"{MAX_DD_PCT:.1f}%  ({MAX_DD_DATE})"),
        ("WETH price, start to end", f"${ETH_START:,.2f} \u2192 ${ETH_END:,.2f}"),
    ]
    yt = 0.235
    for label, val in rows:
        ax.text(0.10, yt, label, fontsize=9.5)
        ax.text(0.68, yt, val, fontsize=9.5, weight="bold")
        yt -= 0.025
    pdf.savefig(fig)
    plt.close(fig)

    # ---------------------------------------------------------------- page 4: gas + operational
    fig, ax = new_page(pdf)
    ax.text(0.08, 0.95, "3. Transaction Cost Model", fontsize=13.5, weight="bold")
    y = 0.905
    y = text_block(ax, 0.08, y, (
        f"The strategy requires exactly two on-chain transactions: one to open the position, "
        f"one to close it. No rebalancing transactions are required between them."
    ))
    y -= 0.02
    tbl = [
        ("Open position (mint)", f"~{GAS_MINT:,} gas"),
        ("Close position (decrease liquidity, collect, burn)", f"~{GAS_EXIT:,} gas"),
        ("Round-trip cost, typical network conditions "
         f"(~{GWEI_TYPICAL:.0f} gwei, WETH ${ETH_FOR_GAS:,.0f})", f"${ROUND_TRIP_TYPICAL:.2f}"),
        ("Round-trip cost, elevated network conditions "
         f"(~{GWEI_SPIKE:.0f} gwei, WETH ${ETH_FOR_GAS:,.0f})", f"${ROUND_TRIP_SPIKE:.2f}"),
    ]
    for label, val in tbl:
        y = text_block(ax, 0.10, y, label, size=9.5, max_width=62)
        ax.text(0.78, y + 0.0215, val, fontsize=9.5, weight="bold")
        y -= 0.012
    y -= 0.015
    y = text_block(ax, 0.08, y, (
        f"At elevated network conditions, position sizes above approximately "
        f"${BREAKEVEN_CAPITAL_1PCT:,.0f} keep round-trip transaction cost under 1% of capital. "
        f"Smaller positions should size this cost explicitly against expected return before "
        f"entry."
    ))

    y -= 0.05
    ax.text(0.08, y, "4. Operational Layer", fontsize=13.5, weight="bold")
    y -= 0.04
    ops = [
        "Custody: a dedicated wallet funded only with the capital allocated to this strategy, "
        "plus a small ETH balance for gas. Hardware-wallet signing for any live deployment.",
        "Position management: Uniswap's NonfungiblePositionManager contract, via the Uniswap "
        "application or a scripted interface. One mint transaction at entry; one "
        "decrease-liquidity-and-collect-and-burn transaction at exit.",
        "Monitoring: position value and pool liquidity checked on a regular cadence (daily is "
        "sufficient for a full-range, non-rebalancing position) against a block explorer or "
        "position-tracking dashboard. No active intervention required between entry and exit.",
        "Accounting: fee realization and position closure are taxable events in most "
        "jurisdictions. Position-level records (entry value, exit value, fees realized) should "
        "be kept for reporting.",
    ]
    for item in ops:
        y = text_block(ax, 0.10, y, "\u2022 " + item, size=9.5, max_width=88)
        y -= 0.012
    pdf.savefig(fig)
    plt.close(fig)

    # ---------------------------------------------------------------- page 5: exit plan + risk
    fig, ax = new_page(pdf)
    ax.text(0.08, 0.95, "5. Exit Plan", fontsize=13.5, weight="bold")
    y = 0.905
    exits = [
        (f"Drawdown limit", f"Exit if position value falls more than {abs(MAX_DD_PCT):.0f}% "
                             f"below its entry value. This is the maximum historical drawdown "
                             f"observed in the backtest; a live position breaching it has moved "
                             f"outside the strategy's tested range."),
        ("Capital-at-risk limit", "Exit if the position's unrealized loss exceeds the pre-set "
                                   "maximum loss for this allocation, set before entry as a "
                                   "fraction of total trading capital, independent of the "
                                   "drawdown limit above."),
        ("Scheduled review", "Review the position at a fixed cadence (quarterly is reasonable "
                              "for a non-rebalancing position) against current pool liquidity, "
                              "current fee income rate, and current gas conditions. Exit if the "
                              "position's trailing fee income rate has fallen persistently below "
                              "the rate needed to justify its risk, not only on a loss trigger."),
        ("Operational exit", "Exit immediately on any sign of a smart-contract incident "
                              "affecting the pool or the Uniswap v3 position-manager contract, "
                              "independent of the position's current value."),
    ]
    for label, body in exits:
        ax.text(0.08, y, label, fontsize=10.5, weight="bold")
        y -= 0.026
        y = text_block(ax, 0.10, y, body, size=9.5, max_width=88)
        y -= 0.018

    y -= 0.02
    ax.text(0.08, y, "6. Risk Disclosures", fontsize=13.5, weight="bold")
    y -= 0.035
    risks = [
        "Past performance, including this backtest, does not indicate future results. The "
        "strategy's return depends on future trading volume, fee income, and price movement in "
        "the pool, none of which are guaranteed to resemble the backtest period.",
        "Impermanent loss is a real, uncapped cost that moves against the position on large "
        "price moves in either direction, independent of fee income.",
        "The strategy carries smart-contract risk: exposure to any vulnerability in the "
        "Uniswap v3 protocol or its position-manager contract, and exposure to the underlying "
        "Ethereum network.",
        "Gas costs are estimated from typical and elevated 2026 network conditions and current "
        "WETH price; both are subject to change and should be re-checked before each "
        "transaction.",
    ]
    for item in risks:
        y = text_block(ax, 0.10, y, "\u2022 " + item, size=9.5, max_width=88)
        y -= 0.012

    y -= 0.03
    ax.text(0.08, y, "Sources", fontsize=11, weight="bold")
    y -= 0.025
    y = text_block(ax, 0.08, y, (
        "Backtest: complete real Uniswap v3 USDC/WETH 0.05% swap history (on-chain, 2021-05-05 "
        "to 2026-09-08). Gas unit estimates: standard Uniswap v3 NonfungiblePositionManager "
        "transaction costs. Gas price range: Ethereum mainnet daily average gas price, 2026."
    ), size=8.5)
    pdf.savefig(fig)
    plt.close(fig)

print(f"written: {OUT}")
print(f"round-trip gas, typical: ${ROUND_TRIP_TYPICAL:.2f} | spike: ${ROUND_TRIP_SPIKE:.2f} | "
      f"breakeven capital (1%): ${BREAKEVEN_CAPITAL_1PCT:,.0f}")
