# Ethereum architecture, security perspective — survey (2026-11-01)

Scope: what changed in Ethereum's ordering/consensus architecture since Daian et al. 2019 ("Flash Boys 2.0"), and what each change does or does not do to the PGA/MEV threat model the paper describes. Search-confirmed claims marked [S]; unconfirmed/dated claims marked [U].

## 1. The Merge (Sept 2022) and PoS consensus
PGAs in the paper assume PoW with `D ~ Exp(λ)` block time and single-miner block assembly. Post-Merge, block proposers are chosen by a known validator schedule (PoS), block time is fixed at 12s slots, and the single-block-producer game simplifies (no race between competing chain tips at the block-interval timescale) but a new off-chain market — **MEV-Boost** — replaced in-protocol ordering as the actual auction mechanism.

## 2. MEV-Boost / Proposer-Builder Separation (off-chain, current default)
Specialized **builders** construct full blocks (bundling arbitrage, including PGA-equivalents) and submit bids to **relays**, which forward only the highest-bid header to the **proposer** (validator), who signs blind and gets paid via the relay. This is the direct institutionalization of the paper's PGA: builders now run what used to be bot-vs-bot gas auctions internally, and the proposer simply sells block space to the highest bidder. Centralization risk: proposer never sees block contents until sealed, so censorship happens at the relay/builder layer, not the validator layer.
- Relay market share is volatile and sources disagree sharply [U]: MEV Watch's live snapshot shows Ultra Sound (~26%) and Titan (~22%) leading, both classed non-censoring, with Flashbots' OFAC-filtering relay down to ~2.8% of blocks [S, mevwatch.info]. Other trackers in 2026 give wildly different numbers (36–90% Flashbots share) — treat any single relay-share figure as unreliable without checking the methodology.
- Post-Merge OFAC-compliant block share: ~51% one month after the Merge, falling to 27% within following months [S, The Block], and censoring-relay share continuing to fall through 2026 per monitoring sites [U].
- **Relevance to the paper:** the paper's miner-level undercutting/time-bandit threat shifts to the builder/relay layer. A relay or large builder is now the entity capable of the paper's Observation-6-style "miner continuously updates to the most profitable set of transactions" behavior.

## 3. Enshrined PBS (ePBS, EIP-7732) — moving the auction into protocol
Bakes the builder/proposer split into consensus itself rather than relying on off-chain relay trust. As of mid-2026, multi-client devnets are stable and ePBS testing was reported largely complete by end of May 2026; target was second-half-2026 mainnet inclusion in the "Glamsterdam" fork [U, secondary sources only — verify against the EIP-7732 page and core-dev call notes before citing as shipped]. One analysis argues ePBS reshapes the proposer-builder relationship but does not by itself decentralize block building [U].
- **Relevance:** removes relay-trust risk (builder payment is enforced by consensus, not an off-chain intermediary), but does not change the underlying economic game — builders still run a sealed-bid auction for the right to order transactions, i.e. the paper's PGA survives, just with a different auctioneer.

## 4. FOCIL — Fork-choice Enforced Inclusion Lists (EIP-7805)
A per-slot committee (reported as 16 validators) builds an inclusion list of transactions that must appear in the next block; attesters refuse to vote for a block that violates it, so enforcement happens at the fork-choice layer. Reported scheduled as the headline feature of the "Hegota" fork following Glamsterdam, second-half/late-2026 target [U, status moved between a Jan-2026 "proposed" framing and a Feb-2026 "scheduled" framing in different sources — not confirmed against a primary dev-call source].
- **Relevance:** this is the most direct mitigation of the paper's core harm (a builder/proposer silently excluding or reordering a user's transaction for profit) — it gives users a channel to force inclusion that bypasses a censoring or profit-maximizing builder. It does not stop reordering of transactions that are included, so sandwich/PGA-style value extraction among included transactions is untouched.

## 5. SUAVE (Flashbots) — decentralized mempool/builder network
Encrypted mempool + decentralized block-building network, explicitly framed by Flashbots as the mitigation for both censorship (post-Tornado-Cash-sanctions relay centralization) and MEV extraction via preference privacy. As of the sources found, SUAVE is still listed as "in development" rather than production, with an earlier SGX-enclave-based builder prototype live on Sepolia testnet [U — no confirmed 2026 production status found; the 2026-dated search hits were page headers, not evidence of shipped milestones]. Flagged for the user to re-verify against Flashbots' own current docs before citing as live infrastructure.

## 6. Intents / batch auctions at the application layer (not consensus)
CoW Protocol (CoW Swap) and UniswapX move the ordering problem off-chain into a solver competition with a uniform clearing price (CoW) or Dutch auction (UniswapX), rather than relying on chain-level ordering fairness at all.
- A TUM master's thesis found actual "coincidence of wants" matches on CoW Protocol are rare, so the batch-auction mechanism's MEV-reduction benefit may come mostly from solver competition and uniform pricing rather than from CoW matching itself [S, thesis-level, not independently re-verified].
- Vendor-sourced claims that CoW Swap "significantly reduces sandwich attacks" trace to EigenPhi reporting that was not independently re-verified here [U].
- Solver trust/collusion is an acknowledged open risk in this design class [S, noted across sources] — structurally this is the same N-agent competitive-cooperative problem the paper's Section V-D models for PGA bidders, just relocated to a solver auction. Directly relevant to our swarm-agent formalization (see `swarm_pga_model.md`).

## 7. Literature survey status
- `SoK: MEV Countermeasures: Theory and Practice` (Yang, Zhang et al., arXiv 2212.05111, first version Dec 2022, later revision Oct 2023) catalogs ~30 countermeasures across four technical directions and is the standard reference taxonomy [S].
- `Maximal Extractable Value Mitigation Approaches in Ethereum and Layer-2 Chains: A Comprehensive Survey` (Alipanahloo, Hafid, Zhang, arXiv 2407.19572, Jul 2024) extends coverage to L2 rollups; points to delay encryption + PBS and shared sequencing as promising directions [S].
- No 2025-dated MEV-countermeasure SoK found in this search pass; a follow-up targeted search (arXiv listing, IEEE S&P/CCS/Financial Crypto proceedings) would be needed for full 2025–2026 coverage before any claim of completeness.

## Sources
- https://ethresear.ch/t/why-enshrine-proposer-builder-separation-a-viable-path-to-epbs/15710
- https://ethresear.ch/t/epbs-design-constraints/18728
- https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870
- https://rig.ethereum.org/post/EIP-7805-Fork-choice-enforced-Inclusion-Lists-(FOCIL)
- https://theccpress.com/ethereum-moves-to-curb-mev-as-epbs-focil-advance
- https://www.mevwatch.info/
- https://www.mevwatch.info/methodology
- https://www.theblock.co/post/230179/ethereums-ofac-compliant-blocks-fall-to-27-marking-a-drop-in-protocol-level-censorship
- https://writings.flashbots.net/mev-for-the-next-trillion
- https://iptf.ethereum.org/vendors/flashbots/
- https://arxiv.org/pdf/2212.05111 (SoK: MEV Countermeasures)
- https://export.arxiv.org/abs/2407.19572 (MEV mitigation survey, L2-inclusive)
- https://arxiv.org/pdf/2403.02525 (intent marketplaces, UniswapX/CoW)

## Caveats
Most 2026-dated claims above come from secondary crypto-news/blog sources, not primary EIP specs or core-dev call minutes. Before using any of §2–5 in a published write-up, re-verify the current fork-inclusion status directly against eips.ethereum.org and the Ethereum core-dev call notes, since this area moves fast and several sources in this pass contradicted each other.
