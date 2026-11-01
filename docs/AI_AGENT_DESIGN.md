# AI Agent Design

Status: **Draft v0.2** — implementation in Phase 7. LLM provider default is Claude; budget **[OPEN #16]**.

## 1. Scope

One customer-facing Hebrew text assistant, scoped to a single order at a single caterer. No caterer-facing agent and no voice in the MVP. **[CONFIRMED]**

## 2. Tools

All tools are thin wrappers around `services/`. Arguments are Pydantic models; invalid arguments are rejected before any service call. The order ID and caterer ID are **bound by the server from the private link token**, never taken from model output. Read tools can therefore only return that caterer's data.

### Read tools

| Tool | Args | Returns |
|---|---|---|
| `get_menu_categories` | — | Active categories |
| `get_available_dishes` | `category_id?`, `vegetarian?`, `vegan?`, `kashrut?` | Dishes with price, unit, dietary fields, calories (null = unknown) |
| `get_dish_details` | `dish_id` | Full dish incl. allergen statuses and calories |
| `get_current_order` | — | Order, items, guest composition, `version` |
| `get_order_pricing` | — | Backend-computed itemized pricing |
| `get_quantity_recommendations` | — | Backend-computed recommendations from the caterer's rules |
| `get_kashrut_check` | — | Caterer kashrut status and the order's mixing result (ok / warn / blocked) |

### Action tool

| Tool | Args | Effect |
|---|---|---|
| `propose_order_change` | `changes: list[Change]`, `rationale: str` | Backend validates → computes diff and price impact → stores `ai_change_proposals` row (`pending`) → returned to UI. **No order mutation.** |

`Change` is a discriminated union: `add_item{dish_id, quantity}`, `remove_item{dish_id}`, `set_quantity{dish_id, quantity}`, `update_details{fields}` (whitelisted fields only).

**Confirmation is not an AI tool.** `confirm_order_change` from the spec is implemented as the customer-only HTTP endpoint `POST /proposals/{id}/approve`, triggered by a UI button. The model cannot approve its own proposals. **[RECOMMENDATION — strengthens Decision 7]**

## 3. Workflow (spec §7)

1. Customer sends a message.
2. Agent interprets it.
3. Agent calls read tools for real data.
4. Agent calls `propose_order_change`.
5. Backend validates: dishes exist, are available, and belong to the order's caterer; quantities > 0 and within rules; fields whitelisted; order is `draft`. A proposal that would create a meat + dairy mix under a `block` rule is rejected.
6. UI shows a diff card: current vs proposed, price difference, Approve / Reject.
7. Customer clicks Approve or Reject.
8. On approve, in **one transaction**: lock order row (`SELECT … FOR UPDATE`), check `proposal.status == pending` and `proposal.base_order_version == order.version`, apply changes, `order.version += 1`, set `executed_at`, `status = approved`.
9. Backend recalculates pricing.
10. Frontend re-renders from the returned persisted order.

## 4. Safety guarantees

| Risk | Control |
|---|---|
| Invented dish | Only `dish_id`s that exist, are available, and belong to the caterer pass validation |
| Invented price | Prices never accepted from the model; computed by `services/pricing` |
| Invented calories | Only stored values are quoted; a null value is reported as unknown, never estimated |
| Cross-caterer data | Caterer ID bound server-side; every tool is scoped to it |
| Runaway AI cost | Per-caterer message limit checked before each LLM call; over the limit → `429 ai_limit_reached`, and ordering still works without chat |
| Silent mutation | No tool mutates orders; only the approve endpoint does |
| Double execution | `status` + `executed_at` checked under row lock; second approve → `409 proposal_not_pending` |
| Stale proposal | `base_order_version` mismatch → proposal marked `expired`, `409 order_version_conflict` |
| Cross-order access | Order ID bound server-side; tool cannot target another order |
| Prompt injection (user text or dish descriptions) | System prompt states business rules are fixed; tool outputs treated as data; authorization never depends on model output |
| Unknown allergen info | Tool returns `unknown`; system prompt requires saying "not verified" and advising to contact the business; no safety guarantees |
| Model/tool failure | Errors returned to the model as structured tool errors; no partial writes (transactional) |
| Logging | Log tool names, IDs, error codes; never API keys; avoid personal data |

## 5. System prompt outline

- Role: assistant for *this* caterer's order builder; the caterer's name is inserted by the server.
- Use tools for every fact about dishes, prices, availability, dietary data.
- Never state a price/quantity not returned by a tool.
- Every change → `propose_order_change`; tell the customer to approve in the card.
- Cannot approve, submit, or reject orders.
- Unknown dietary/allergen data → say it is unknown.
- Unknown calories → say they are unknown; never estimate.
- Kashrut: state only the caterer's stored status; never rule on what is or isn't kosher.
- Language: always reply in Hebrew.

## 6. Tests (Phase 7, required by spec §11)

Proposal creation · approve mutates exactly once · reject doesn't mutate · duplicate approve rejected · stale version rejected · invalid/unavailable dish rejected · another caterer's dish rejected · missing dietary data and calories reported as unknown · approve without the order's token forbidden · approve on non-draft order rejected · blocked kashrut mix rejected · usage limit enforced. LLM is mocked in tests; the safety lives in services, so it is testable without a model.
