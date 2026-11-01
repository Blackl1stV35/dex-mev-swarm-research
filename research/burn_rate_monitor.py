"""Burn-rate monitor for Claude Pro usage on this project.

Two independent signals, logged to burn_rate_log.csv:
  1. harness_total_tokens_left: the token-left counter this harness shows me each turn.
     Directional only -- not confirmed to be the same meter as the Pro usage screen.
  2. claude_pro_meter: session_pct_used / weekly_pct_used, read by the USER from the
     app's Usage screen and reported to me as a screenshot. This is the authoritative
     Pro-plan meter; I cannot query it myself.

Usage: append a row to burn_rate_log.csv after each reading, then run this script to
get a burn-rate estimate and a go/no-go recommendation for a heavy job.
"""
import csv
import sys
from datetime import datetime, timedelta

LOG = "burn_rate_log.csv"

# Heavy-job threshold: do not start a multi-agent workflow if projected to cross
# either limit before its own reset.
HEAVY_JOB_TOKEN_COST_ESTIMATE = 400_000  # typical workflow in this project's history


def load_rows(path=LOG):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def parse_ts(s):
    return datetime.fromisoformat(s)


def harness_burn_rate(rows):
    pts = [(parse_ts(r["logged_at_utc"]), float(r["value"])) for r in rows
           if r["source"] == "harness_total_tokens_left"]
    pts.sort(key=lambda p: p[0])
    if len(pts) < 2:
        return None
    (t0, v0), (t1, v1) = pts[0], pts[-1]
    dt_s = max((t1 - t0).total_seconds(), 1.0)
    return (v0 - v1) / dt_s  # tokens consumed per second, directional


def pro_meter_status(rows):
    latest = {}
    for r in rows:
        if r["source"] != "claude_pro_meter":
            continue
        latest[r["metric"]] = (parse_ts(r["logged_at_utc"]), float(r["value"]))
    return latest


def recommend(rows):
    rate = harness_burn_rate(rows)
    meter = pro_meter_status(rows)
    print("=== Burn-rate monitor ===")
    if rate is not None:
        print(f"harness token burn rate: {rate:.1f} tokens/s (directional, 2+ readings)")
    else:
        print("harness token burn rate: insufficient readings (need >=2 harness rows)")

    if "session_pct_used" in meter:
        ts, pct = meter["session_pct_used"]
        print(f"Pro session usage: {pct:.0f}% used as of {ts.isoformat()} (resets per app)")
        if pct >= 70:
            print("  -> HOLD: session usage high, avoid heavy multi-agent jobs until reset")
        elif pct >= 40:
            print("  -> CAUTION: moderate usage, keep heavy jobs small and single-pass")
        else:
            print("  -> OK: room for one moderate job this session")
    else:
        print("Pro session usage: no reading logged yet -- ask the user for a screenshot")

    if "weekly_pct_used" in meter:
        ts, pct = meter["weekly_pct_used"]
        print(f"Pro weekly usage: {pct:.0f}% used as of {ts.isoformat()}")
        if pct >= 60:
            print("  -> HOLD: weekly budget tight, defer non-essential workflows to next week")

    print("\nRecommendation inputs only; final go/no-go is a judgment call using both signals.")


if __name__ == "__main__":
    rows = load_rows(sys.argv[1] if len(sys.argv) > 1 else LOG)
    recommend(rows)
