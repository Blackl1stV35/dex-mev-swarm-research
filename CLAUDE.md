# dex-mev-swarm-research — project context

Research-only. No live orders, no mainnet transactions, no real-capital deployment. Pure-revenue arbitrage / PGA / MEV study extending Daian et al. 2019 ("Flash Boys 2.0", arXiv:1904.05234). Swarm-agent work means **simulated competing strategy agents in a backtested or synthetic market environment**, never agents acting against real counterparties' live orders.

## Scope (set 2026-11-01)
1. Formal + simulated extension of the paper's PGA game to N>2 players ("swarm"), reusing problem 29 (N-sellers-shared-model) machinery from `market-dynamics-research`.
2. Ethereum architecture security survey (post-2019: PBS, MEV-Boost, relays, encrypted mempools, inclusion lists, based rollups).
3. Literature follow-up on the paper's own Section VIII open questions — checked against 2020–2026 work, one row per question.
4. Token-burn-rate monitor (Claude Pro plan; see `../xauusd_system` memory `feedback-claude-pro-plan-usage-limits.md`).

## Context & memory management policy
- **Persistent memory lives outside this repo**: `C:\Users\user\.claude\projects\D--xauusd-system\memory\` (shared index, `MEMORY.md`). This repo's `memory_pointer/` holds only a local index of which memory files are relevant here — never duplicate memory content into the repo.
- **Every finding that should survive a context reset** gets written to a memory file immediately (not batched at session end), per standing-mode rule 1.
- **Large reads delegate to subagents or scripts**, not pasted into the main thread (standing-mode rule 10). Pro-plan quota: prefer direct scripts over agent fan-out; use at most one narrow agent per adversarial check, only on a finished result.
- **Each research unit is pre-registered** (hypothesis + gates before computing), same discipline as `xauusd_system`/`market-dynamics-research`.

## In-loop workflow / model-switching
- Default model: current session default (set via `/model`, currently Sonnet 5, medium effort).
- Switch up (opus/higher effort) only for: proving a new theorem step, adversarial verification of a finished result, or security-survey synthesis across many sources.
- Switch down (haiku/low effort) for: mechanical data pulls, log parsing, file staging.
- A `/loop` invocation (dynamic pacing) is used for the burn-rate monitor only — see `research/burn_rate_monitor.py` and the memory file `feedback-claude-pro-plan-usage-limits.md`. It does not drive the research work itself; that stays interactive.

## Related repos (read cross-references, do not edit without the standing authorization already on file)
- `D:\xauusd_system` — XAUUSD/FX meta-policy, AFML studies, breach-cap studies.
- `D:\market-dynamics-research` — pure-math problems 1-29, problem 14 (LVR), 28 (AMM), 29 (N-seller shared model), 5/16 (N-player rigidity).
