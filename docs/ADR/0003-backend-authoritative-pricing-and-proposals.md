# ADR 0003 — Backend-authoritative pricing and approval-gated AI proposals

Status: Accepted (Phase 0) · Date: 2026-10-29

## Context
Decisions 6 and 7: deterministic backend pricing; every AI change needs explicit customer approval.

## Decision
- Pricing and quantities are computed only in `services/`.
- The AI can only create proposals (`ai_change_proposals`). Execution happens through a customer-only HTTP endpoint, never an AI tool.
- Execution is transactional with optimistic locking (`orders.version`) and single-use proposals (`executed_at`).
- Submission freezes a price snapshot on `order_items`.

## Consequences
+ The model can be wrong without corrupting orders or prices.
+ Safety rules are unit-testable without an LLM.
− Every order mutation must carry a `version`, which adds a little client complexity.
