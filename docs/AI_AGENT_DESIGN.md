# AI Agent Design

Status: **v1.0, implemented in Phase 4** (`backend/app/agents/`). LLM provider: Anthropic Claude, model `claude-sonnet-5-5` (OPEN #16 decided 2026-11-04).

## 1. Scope

One customer-facing assistant, scoped to a single order. No admin agent. **[CONFIRMED]**

## 2. Tools

All tools are thin wrappers around `services/`. Arguments are Pydantic models; invalid arguments are rejected before any service call. The order ID is **bound by the server from the request context**, never taken from model output.

### Read tools

The menu is small, so one `get_menu` call replaces the planned category, dish-list and dish-detail tools, and pricing is part of `get_current_order`.

| Tool | Args | Returns |
|---|---|---|
| `get_menu` | — | Orderable dishes with category, price, unit, minimum, servings per unit, kashrut, vegetarian/vegan (null = unknown) and allergens (missing = unknown) |
| `get_current_order` | — | Status, event and guest composition, fulfillment, backend-computed itemized pricing |
| `get_quantity_recommendations` | — | Backend-computed recommendations (OPEN #3 rules) |

### Action tool

| Tool | Args | Effect |
|---|---|---|
| `propose_order_change` | `changes: list[Change]`, `rationale: str` | Backend validates → computes diff and price impact at live catalog prices → stores an `order_proposals` row with `proposed_by = assistant` (`pending`, the same table as owner proposals, migration 0009) → shown as a card under the reply. A new proposal cancels the open one. **No order mutation.** |

`Change` is `{op, dish_id, quantity}` with `op` in `add_item`, `set_quantity` (quantity required) or `remove_item` (quantity null). Event details are not changed by the assistant (the customer edits them in the event form); `update_details` was dropped.

**Confirmation is not an AI tool.** `confirm_order_change` from the spec is implemented as the customer-only HTTP endpoint `POST /api/orders/{id}/proposals/{pid}/accept`, triggered by a UI button. The model cannot approve its own proposals. **[RECOMMENDATION — strengthens Decision 7]**

## 3. Workflow (spec §7)

1. Customer sends a message.
2. Agent interprets it.
3. Agent calls read tools for real data.
4. Agent calls `propose_order_change`.
5. Backend validates: dishes exist & available, quantities > 0 and within rules, fields whitelisted, order is `draft`.
6. UI shows a diff card: current vs proposed, price difference, Approve / Reject.
7. Customer clicks Approve or Reject.
8. On approve, in **one transaction**: check `proposal.status == pending` and `proposal.base_order_version == order.version`, apply changes, then a conditional `UPDATE` bumps `order.version` only if it is still at the base version and the order is still a draft (the order stays `draft`), and the proposal moves to `accepted`. Otherwise the proposal expires (`409 proposal_expired`).
9. Backend recalculates pricing.
10. Frontend re-renders from the returned persisted order.

### Loop (implemented)

- Claude Messages API through the official `anthropic` SDK, manual tool loop, at most 8 model calls per customer message. Adaptive thinking, `effort: medium`, prompt caching (`cache_control`), and the server-side refusal fallback (`fallbacks: "default"`).
- Tools are `strict` JSON schemas and are validated again with Pydantic before any service call. Errors (validation or `AppError`) go back to the model as `is_error` tool results.
- History is stored per order in `ai_conversations` / `ai_messages` exactly as exchanged (thinking blocks included) and only appended. A turn's model messages are stored together when it finishes, so a failed call never leaves a tool call without its result.
- `refusal`, `max_tokens` or the round limit end the turn with a fixed Hebrew fallback reply.
- Budget: `business_settings.assistant_daily_limit` messages per customer in any 24 hours (default 30, 0 = off) → `429 assistant_limit`. No API key → `503 assistant_unavailable` and the panel stays hidden.
- On accept, an assistant proposal writes the items, bumps `version` and keeps the order a draft (prices stay live). Submitting the order expires an open proposal.

## 4. Safety guarantees

| Risk | Control |
|---|---|
| Invented dish | Only `dish_id`s that exist and are available pass validation |
| Invented price | Prices never accepted from the model; computed by `services/pricing` |
| Silent mutation | No tool mutates orders; only the approve endpoint does |
| Double execution | `status` + `executed_at` checked under row lock; second approve → `409 proposal_not_pending` |
| Stale proposal | `base_order_version` mismatch → proposal marked `expired`, `409 order_version_conflict` |
| Cross-order access | Order ID bound server-side; tool cannot target another order |
| Prompt injection (user text or dish descriptions) | System prompt states business rules are fixed; tool outputs treated as data; authorization never depends on model output |
| Unknown allergen info | Tool returns `unknown`; system prompt requires saying "not verified" and advising to contact the business; no safety guarantees |
| Model/tool failure | Errors returned to the model as structured tool errors; no partial writes (transactional) |
| Logging | Log tool names, IDs, error codes; never API keys; avoid personal data |

## 5. System prompt outline

- Role: assistant for *this* catering business's order builder.
- Use tools for every fact about dishes, prices, availability, dietary data.
- Never state a price/quantity not returned by a tool.
- Every change → `propose_order_change`; tell the customer to approve in the card.
- Cannot approve, submit, or reject orders.
- Unknown dietary/allergen data → say it is unknown.
- Language: Hebrew (OPEN #12 decided).

## 6. Tests (Phase 4, required by spec §11)

Proposal creation · approve mutates exactly once · reject doesn't mutate · duplicate approve rejected · stale version rejected · invalid/unavailable dish rejected · missing dietary data reported as unknown · approve by another customer forbidden · approve on non-draft order rejected. LLM is mocked in tests; the safety lives in services, so it is testable without a model.
