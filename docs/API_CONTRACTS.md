# API Contracts (preliminary)

Status: **Customer submission implemented; remaining lifecycle is a draft target**.

## Implemented customer flow

- `GET /api/catalog`: dishes and delivery zones from SQLite, using the existing demonstration prices.
- `POST /api/orders`: submits the complete quotation (not a draft). Body: `contact`, `event`,
  `items` (dish ID to quantity), `expected_total_minor`. Returns the persisted UI order shape.
  The server validates data, prices from its catalog and saves everything in one transaction.
  Price mismatch returns 409 instead of silently accepting a changed total.
- `GET /api/orders/{id}`: retrieve a submitted order.
- `GET /api/orders/receipt`: recover by credential when the submission response was lost.
- All order calls require `X-Order-Token`, 32 random bytes encoded as 64 lowercase hexadecimal
  characters. The browser persists it before sending; the database stores only its SHA-256 hash.
  It is a bearer capability for one order, not a customer login. Never put it in URLs/logs.
  Clearing browser storage loses access; cross-device/account recovery remains future work.
- Repeated submission with the same token and same normalized body returns the existing order
  (200); a changed body returns 409. Initial creation returns 201 only after commit.
- Reads return `Cache-Control: no-store`. Missing/wrong credentials cannot enumerate order details.
- Current errors use FastAPI's `detail` format, handled by the frontend wrapper.

The lifecycle tables below describe future endpoints. Their draft `POST /api/orders` semantics
are superseded by the complete-submission flow above for this increment. Drafts remain local;
submission freezes item names, units, quantities and prices. No owner approval or AI endpoint
is implemented by this increment. Dates/slots/fees are still demonstration business rules.

Base: same origin as the frontend. JSON only. All bodies validated with Pydantic.

## Error format

```json
{ "error": { "code": "order_version_conflict", "message": "Human readable", "details": {} } }
```

Common codes: `validation_error` (422), `not_found` (404), `forbidden` (403), `unauthenticated` (401), `invalid_transition` (409), `order_version_conflict` (409), `proposal_not_pending` (409).

## System

| Method | Path | Response | Phase |
|---|---|---|---|
| GET | `/health` | `{"status":"ok","env":"development"}` | **1 (implemented)** |

## Catalog (public read)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/catalog/categories` | Active categories, ordered |
| GET | `/api/catalog/dishes?category_id=&vegan=&vegetarian=&kashrut=` | Available dishes with price, unit, dietary info (unknown fields returned as `null`) |
| GET | `/api/catalog/dishes/{id}` | Dish detail incl. allergen statuses |
| GET | `/api/availability?from=&to=` | Blocked dates + slots |

## Customer orders (auth model **[OPEN #1]**)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders` | Create draft from event config |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | Set quantity; requires `version` |
| DELETE | `/api/orders/{id}/items/{dish_id}` | Remove dish; requires `version` |
| GET | `/api/orders/{id}/pricing` | Itemized breakdown |
| GET | `/api/orders/{id}/recommendations` | Quantity recommendations (rules **[OPEN #3]**) |
| POST | `/api/orders/{id}/submit` | `draft → pending_approval`; freezes snapshot |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

## AI assistant (Phase 4)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders/{id}/chat` | `{message}` → `{reply, proposals:[...]}` |
| GET | `/api/orders/{id}/proposals?status=pending` | |
| POST | `/api/orders/{id}/proposals/{pid}/approve` | Executes in one transaction if `base_order_version == order.version` and status `pending` |
| POST | `/api/orders/{id}/proposals/{pid}/reject` | No mutation |

Proposal shape:

```json
{
  "id": "uuid",
  "base_order_version": 7,
  "changes": [
    {"op": "add_item", "dish_id": "uuid", "quantity": 2},
    {"op": "set_quantity", "dish_id": "uuid", "quantity": 4},
    {"op": "remove_item", "dish_id": "uuid"},
    {"op": "update_details", "fields": {"requested_at": "..."}}
  ],
  "diff": [{"label": "...", "current": "...", "proposed": "..."}],
  "price_before": "1200.00",
  "price_after": "1350.00",
  "status": "pending"
}
```

## Admin (owner only)

| Method | Path |
|---|---|
| GET/POST | `/api/admin/categories` · PATCH/DELETE `/api/admin/categories/{id}` |
| GET/POST | `/api/admin/dishes` · PATCH/DELETE `/api/admin/dishes/{id}` |
| POST | `/api/admin/dishes/{id}/image` (multipart → Supabase Storage) |
| PUT | `/api/admin/dishes/{id}/dietary` |
| GET/POST/PATCH/DELETE | `/api/admin/delivery-zones` |
| GET/POST/PATCH/DELETE | `/api/admin/time-slots` |
| GET/POST/DELETE | `/api/admin/blocked-dates` |
| GET | `/api/admin/orders?status=` · GET `/api/admin/orders/{id}` |
| POST | `/api/admin/orders/{id}/approve` · `/api/admin/orders/{id}/reject` `{note}` |

## Order status transitions

| Transition | Endpoint | Allowed actor |
|---|---|---|
| draft → pending_approval | `POST /api/orders/{id}/submit` | Order's customer |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | Owner |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | Owner |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
