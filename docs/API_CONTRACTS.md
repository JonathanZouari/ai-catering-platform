# API Contracts (preliminary)

Status: **Draft v0.2**. Only `GET /health` is implemented (Phase 1). Everything else is a design target and may change.

Base: same origin as the frontend. JSON only. All bodies validated with Pydantic.

**Caterer scope:** public routes take it from `{slug}`, order routes from `X-Order-Token`, and `/api/admin/*` from the caterer user's login. No request body ever names a caterer. Another caterer's resource returns `404`.

## Error format

```json
{ "error": { "code": "order_version_conflict", "message": "Human readable", "details": {} } }
```

Common codes: `validation_error` (422), `not_found` (404), `forbidden` (403), `unauthenticated` (401), `conflict` (409), `invalid_transition` (409), `order_version_conflict` (409), `proposal_not_pending` (409), `kashrut_mixing_blocked` (409), `kashrut_warning_not_acknowledged` (409), `ai_limit_reached` (429). `message` is Hebrew; `code` stays English.

## System

| Method | Path | Response | Phase |
|---|---|---|---|
| GET | `/health` | `{"status":"ok","env":"development"}` | **1 (implemented)** |

## Catalog (public read)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/c/{slug}` | Public caterer profile: name, logo, color, kashrut status |
| GET | `/api/c/{slug}/catalog/categories` | Active categories, ordered |
| GET | `/api/c/{slug}/catalog/dishes?category_id=&vegan=&vegetarian=&kashrut=` | Available dishes with price, unit, dietary info, calories (unknown fields returned as `null`) |
| GET | `/api/c/{slug}/catalog/dishes/{id}` | Dish detail incl. allergen statuses |
| GET | `/api/c/{slug}/availability?from=&to=` | Blocked dates + slots |

## Customer orders (private link, ADR 0006)

Every route except order creation requires `X-Order-Token`. The token must match the order in the path.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/c/{slug}/orders` | Create draft from name, phone, and event config. The response includes the token, returned this one time only |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | Set quantity; requires `version` |
| DELETE | `/api/orders/{id}/items/{dish_id}` | Remove dish; requires `version` |
| GET | `/api/orders/{id}/pricing` | Itemized breakdown |
| GET | `/api/orders/{id}/recommendations` | Quantity recommendations from the caterer's rules |
| GET | `/api/orders/{id}/kashrut-check` | `{status: ok \| warn \| blocked}` per the caterer's mixing rule |
| POST | `/api/orders/{id}/submit` | `draft → pending_approval`; freezes snapshot. Rejected if mixing is blocked, or if a warning wasn't acknowledged via `{acknowledge_kashrut_warning: true}` |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

## AI assistant (Phase 7)

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

## Admin (logged-in caterer user, own caterer only)

| Method | Path |
|---|---|
| GET/PATCH | `/api/admin/profile` (name, branding, kashrut status, mixing rule) · POST `/api/admin/profile/logo` · POST `/api/admin/profile/kashrut-certificate` |
| GET | `/api/admin/quantity-rules` · PUT `/api/admin/quantity-rules/{category_id}` · DELETE (revert to platform default) |
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
| draft → pending_approval | `POST /api/orders/{id}/submit` | Holder of the order's private link |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | The order's caterer |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | The order's caterer |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
