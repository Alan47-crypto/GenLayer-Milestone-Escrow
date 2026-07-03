# GenLayer Milestone Escrow Adjudicator

An Intelligent Contract primitive built on GenLayer that evaluates and adjudicates gig work, bounties, and decentralized milestones using multi-validator AI consensus. 

## Overview
Traditional smart contracts require centralized oracles or human multi-sig signers to resolve subjective real-world outcomes (e.g., "Did the developer deliver the code according to the specification?"). 

The **Milestone Escrow Adjudicator** replaces the human middleman with GenLayer's Optimistic Democracy consensus mechanism[cite: 1]. It allows clients to lock funds in escrow with a specific natural language specification. Once the worker submits their evidence URL, decentralized LLM validators independently parse the deliverables, grade the work against the original specification, and release the funds if the quality meets the strict programmatic thresholds[cite: 1].

## Architectural Highlights

This contract is designed as a reusable primitive and demonstrates advanced Intelligent Contract capabilities:

* **Custom Consensus with `run_nondet_unsafe`:** Instead of relying on rigid, exact-string matching (`strict_eq`), this contract implements a custom leader/validator pairing[cite: 1]. This safely handles the non-deterministic nature of LLM reasoning[cite: 1].
* **Strict Numeric Tolerances:** Validators independently re-run the evidence evaluation[cite: 1]. The contract enforces a mathematical $\pm 1$ tolerance on the proposed `quality_score`[cite: 1]. If the leader proposes an 8, validators must independently score it a 7, 8, or 9 for the transaction to reach consensus.
* **Deterministic Rejection Gates:** If any validator scores the submission below a 5, the contract overrides the AI's subjective reasoning and forces a `DISPUTED` state, protecting client funds.
* **Defensive Error Handling:** Any API failures, malformed URLs, or JSON parsing errors during the web-fetching phase are caught by the validator error classification logic, resulting in a safe `UNDETERMINED` state (disagreement) rather than corrupting the blockchain state[cite: 1].
* **Absolute Time Fallbacks:** Includes a `claim_expired_refund` function that uses the deterministic transaction timestamp (`datetime.now(timezone.utc).timestamp()`) to allow client clawbacks if the worker misses the deadline[cite: 1].

## Core Functions

* `create_bounty(worker_hex, deadline_timestamp, specification)`: Locks GEN value in escrow and defines the work requirements.
* `submit_work(bounty_id, evidence_url)`: Allows the assigned worker to submit a URL containing their deliverable (code, text, or documentation).
* `adjudicate_milestone(bounty_id)`: Triggers the non-deterministic GenVM block[cite: 1]. The network fetches the web data, evaluates it against the specification, and updates the state to `COMPLETED` (triggering payout) or `DISPUTED`.
* `get_bounty_status(bounty_id)`: A view method returning the current status and consensus-approved quality score.

## How to Test in GenLayer Studio

1. Load `MilestoneEscrowAdjudicator.py` into GenLayer Studio and Deploy.
2. Call `create_bounty` with a funded value, a future Unix timestamp, and a specific requirement (e.g., `"A comprehensive text explaining the movement rules of pieces in the game of Chess."`).
3. Switch to the worker's address and call `submit_work` with an evidence URL (e.g., `https://en.wikipedia.org/wiki/Rules_of_chess`).
4. Call `adjudicate_milestone` and watch the validators reach consensus on the quality score.

## Author
Built by Alan47-crypto for the GenLayer ecosystem.
