"""Monte Carlo test of the swarm-dominance proposition in swarm_pga_model.md.

Simulation only, synthetic auction instances. No live network, no real transactions,
no deployment against real counterparties.

PGA mechanics (paper's model, n-player reactive-counterbidding generalization):
  - Opportunity value normalized to $1 (paper's "dollar auction" convention incl. gas).
  - Auction duration D ~ Exp(lambda); mined at t_end.
  - Each independent agent i has latency delta_i: observes others' bids only after delta_i.
  - Reactive counterbidding: on seeing a new best observed bid b, agent rebids
    max(b*(1+iota), b+eps) if profitable, i.e. while next bid <= 1 - c (paper's
    Observation 4 stopping rule: stop raising once a further raise is no longer
    profitable even conditional on winning).
  - Loss function ell(b) = c_loss * b (fraction of last bid paid as gas, paper's
    "partial all-pay" convention; c_loss is small).
  - A swarm of size k fields ONE effective bidder against the (n-k) independent
    competitors (internal non-competition per swarm_pga_model.md section 2-3);
    swarm payoff from a win is split k ways.

Predictions to test (pre-registered in swarm_pga_model.md section 4):
  (i)   per-member swarm payoff >= independent-competitor payoff, gap widens in k
  (ii)  gap shrinks toward 0 as outside-competitor latency -> 0
  (iii) total revenue to the miner (winning bid) falls as k grows
"""
import numpy as np

RNG = np.random.default_rng(20261101)

S = 1.0 / 32.0        # minimum starting bid (paper's "s")
IOTA = 0.125           # minimum bid increment (paper's observed Parity default, 12.5%)
C_LOSS = 0.02          # fraction of last bid lost by losers (gas cost proxy)
LAMBDA = 1.0 / 15.0    # mean block interval 15s (paper's PoW-era parameter)
N_TRIALS = 20_000


def max_profitable_bid():
    """Largest bid b with b <= 1 - C_LOSS (paper's Observation 4 stopping rule), on the
    s*(1+iota)^i grid."""
    b = S
    while b * (1 + IOTA) <= 1 - C_LOSS:
        b *= (1 + IOTA)
    return b


B_MAX = max_profitable_bid()


def run_auction(n_outside, swarm_latency, outside_latency_mean, rng):
    """One PGA instance: 1 swarm bidder (if swarm active) vs n_outside independent
    competitors, OR (if swarm_latency is None) n_outside+1 fully independent competitors
    for the baseline-no-swarm case. Returns (winner_is_swarm, winning_bid, n_bidders)."""
    n_bidders = n_outside + (1 if swarm_latency is not None else 0)
    latencies = rng.exponential(outside_latency_mean, size=n_outside)
    if swarm_latency is not None:
        latencies = np.append(latencies, swarm_latency)
        is_swarm = np.zeros(n_bidders, dtype=bool)
        is_swarm[-1] = True
    else:
        is_swarm = np.zeros(n_bidders, dtype=bool)

    t_end = rng.exponential(1.0 / LAMBDA)
    # event-driven: each bidder's own next-bid time = max(last_seen_update_time, own_delay)
    # simplified continuous approximation: bidder i raises every time it observes a strictly
    # higher best bid, after its own latency delay; iterate in small time steps is wasteful,
    # so instead simulate via a priority-queue-free approximation: round-based reactive
    # bidding converges to the same terminal state (who holds the highest bid at t_end) as
    # the paper's continuous model, since bids are monotone non-decreasing and bounded by
    # B_MAX -- we just need the FINAL bid vector at t_end, not the full path.
    cur_bid = np.full(n_bidders, 0.0)
    cur_bid[np.argmax(rng.random(n_bidders))] = S  # one arbitrary opener at s
    # reactive escalation until no one wants to / can respond before t_end, or bids cap out
    t = 0.0
    last_move_time = np.zeros(n_bidders)
    active = True
    steps = 0
    while active and steps < 200:
        steps += 1
        active = False
        best = cur_bid.max()
        for i in range(n_bidders):
            if cur_bid[i] >= best:
                continue
            resp_time = last_move_time[i] + latencies[i]
            if resp_time >= t_end:
                continue
            nxt = max(best * (1 + IOTA), S)
            if nxt > B_MAX:
                continue
            cur_bid[i] = nxt
            last_move_time[i] = resp_time
            active = True
    win_idx = int(np.argmax(cur_bid))
    return bool(is_swarm[win_idx]), float(cur_bid[win_idx]), n_bidders


def sweep_k(n_total, outside_latency_mean, swarm_latency, n_trials=N_TRIALS):
    """all_winning_bids tracks the MINER's revenue for every auction regardless of winner
    identity (tests prediction iii: total market revenue). swarm_win_bids tracks revenue
    only on the subset of auctions the swarm wins (used for swarm per-member payoff)."""
    rows = []
    for k in range(1, n_total):  # k swarm members, n_total-k outside competitors
        n_outside = n_total - k
        wins = 0
        all_winning_bids = np.empty(n_trials)
        swarm_win_bids = []
        for t in range(n_trials):
            won, bid, _ = run_auction(n_outside, swarm_latency, outside_latency_mean, RNG)
            all_winning_bids[t] = bid
            if won:
                wins += 1
                swarm_win_bids.append(bid)
        win_rate = wins / n_trials
        avg_miner_revenue = float(all_winning_bids.mean())
        swarm_total_payoff = win_rate * (np.mean([1 - b for b in swarm_win_bids]) if swarm_win_bids else 0.0)
        swarm_payoff_per_member = swarm_total_payoff / k
        rows.append(dict(k=k, n_outside=n_outside, win_rate=win_rate,
                          avg_miner_revenue=avg_miner_revenue,
                          swarm_payoff_per_member=swarm_payoff_per_member))
    return rows


def independent_baseline(n_total, outside_latency_mean, n_trials=N_TRIALS):
    """No swarm: n_total fully independent competitors, uniform latency. Per-capita payoff
    and market revenue, for comparison at k=1 (every agent 'independent')."""
    wins_by_agent = np.zeros(n_total)
    revenue = []
    for _ in range(n_trials):
        won, bid, nb = run_auction(n_total - 1, outside_latency_mean, outside_latency_mean, RNG)
        # here "swarm" is just agent n_total-1 playing the identical strategy as everyone else
        revenue.append(bid)
        if won:
            wins_by_agent[-1] += 1  # symmetric agents -> any index representative
    win_rate = wins_by_agent[-1] / n_trials
    per_capita_payoff = win_rate * np.mean([(1 - r) for r in revenue])
    avg_revenue = np.mean(revenue)
    return per_capita_payoff, avg_revenue


if __name__ == "__main__":
    N_TOTAL = 6
    OUTSIDE_LAT_MEAN = 0.4   # seconds, matches paper's measured ~0.4s latency
    SWARM_LAT = 0.4          # swarm's effective bidder has the SAME latency class (fair test)

    print(f"=== Max profitable bid grid cap B_MAX = {B_MAX:.4f} ===\n")

    base_payoff, base_revenue = independent_baseline(N_TOTAL, OUTSIDE_LAT_MEAN)
    print(f"Baseline (all {N_TOTAL} fully independent, symmetric latency {OUTSIDE_LAT_MEAN}s):")
    print(f"  per-capita payoff = {base_payoff:.5f}, avg winning bid (miner revenue) = {base_revenue:.5f}\n")

    print(f"Swarm sweep (n_total={N_TOTAL}, outside latency mean={OUTSIDE_LAT_MEAN}s, swarm latency={SWARM_LAT}s):")
    print(f"{'k':>3} {'n_outside':>9} {'win_rate':>9} {'miner_revenue':>14} {'per-member payoff':>18} {'vs baseline':>12}")
    rows = sweep_k(N_TOTAL, OUTSIDE_LAT_MEAN, SWARM_LAT)
    for r in rows:
        ratio = r["swarm_payoff_per_member"] / base_payoff if base_payoff > 0 else float("nan")
        print(f"{r['k']:>3} {r['n_outside']:>9} {r['win_rate']:>9.4f} {r['avg_miner_revenue']:>14.5f} "
              f"{r['swarm_payoff_per_member']:>18.5f} {ratio:>12.3f}x")
    print(f"(prediction iii check: miner revenue should fall as k grows; baseline k=0-equivalent miner revenue = {base_revenue:.5f})")

    print("\n=== Prediction (ii): gap vs outside-competitor latency (k=3 swarm, sweep outside latency) ===")
    print(f"{'outside_lat':>12} {'swarm_payoff/member':>20} {'baseline_payoff':>16} {'ratio':>8}")
    for lat in [0.05, 0.1, 0.2, 0.4, 0.8, 1.6]:
        rows_k3 = sweep_k(N_TOTAL, lat, SWARM_LAT, n_trials=8000)
        k3 = next(r for r in rows_k3 if r["k"] == 3)
        bp, _ = independent_baseline(N_TOTAL, lat, n_trials=8000)
        ratio = k3["swarm_payoff_per_member"] / bp if bp > 0 else float("nan")
        print(f"{lat:>12.2f} {k3['swarm_payoff_per_member']:>20.5f} {bp:>16.5f} {ratio:>8.3f}x")
