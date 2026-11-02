# API Contracts (preliminary)

Status: **Draft v0.1**. Only `GET /health` is implemented (Phase 1). Everything else is a design target and may change.

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
| GET | `/api/delivery/cities` | `[{city, fee}]` for active zones |
| GET | `/api/availability?from=&to=` | `{earliest_date, blocked_dates, time_slots, full_slots: [{slot_id, date}]}`. Only which slot is full, never booking counts |

## Customer account (Supabase Auth access token as `Authorization: Bearer`, ADR 0005)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/auth/config` | Public: `{supabase_url, supabase_anon_key}` for supabase-js; 503 `auth_unavailable` if not configured |
| GET | `/api/me` | `{email, profile: {full_name, phone} \| null}`; profile is null until first save |
| PUT | `/api/me` | `{full_name, phone}`; creates the customer on first save; email always from the token |
| GET | `/api/me/orders` | The signed-in customer's orders only, any status, newest event first |

## Customer orders (same customer auth; owner = the signed-in customer)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders` | Create draft from event config |
| GET | `/api/orders/{id}` | Order with items, live pricing, `version` |
| PATCH | `/api/orders/{id}` | Update event/fulfillment details; requires `version` |
| PUT | `/api/orders/{id}/items/{dish_id}` | `{quantity, version}`. Whole units, or 0.5 kg steps for weight dishes; ≥ the dish minimum (`422 below_minimum`); the dish must be orderable (`422 dish_unavailable`) |
| DELETE | `/api/orders/{id}/items/{dish_id}?version=N` | Remove dish |
| GET | `/api/orders/{id}/pricing` | `{currency: ILS, vat_included: true, lines[], subtotal, delivery_fee, total}`. Lines are rounded half-up to the agora; a dish no longer orderable is flagged `available: false` and left out of the total |
| GET | `/api/orders/{id}/recommendations` | `[{dish_id, quantity, eligible_guests}]` for dishes with `serves_adults` (rules: OPEN_DECISIONS #3, decided) |
| POST | `/api/orders/{id}/submit` | `{version}`. `draft → pending_approval`. Re-checks everything: dishes still orderable (`409 items_unavailable`), date and lead time, slot, and capacity (`409 slot_full`); `422 empty_order`. Freezes the price snapshot and totals, and emails the owner |
| POST | `/api/orders/{id}/withdraw` | `{version}`. `pending_approval → draft` (OPEN #7); unfreezes prices. After a decision → `409 invalid_transition` |

Every mutation returns the full updated order (new `version`). A stale `version` → `409 order_version_conflict`.

Implemented so far (Phase 3, slice 2): `POST`, `GET` and `PATCH /api/orders/{id}`. Body:

```json
{
  "event": {"event_type": "ברית", "event_date": "2026-12-06", "adults": 30, "children": 4,
            "vegetarian_guests": 6, "vegan_guests": 2, "restricted_guests": 0, "dietary_notes": null},
  "fulfillment_type": "pickup",
  "slot_id": "uuid",
  "delivery_address": null,
  "delivery_city": null
}
```

`PATCH` takes the same full body plus `version`. The rules are enforced server-side:
- The date is not in the past (Israel time) and not blocked → `422 date_unavailable`.
- The slot is active, of the same type, and valid for that weekday → `422 slot_unavailable`. `requested_at` is the event date at the slot's start time, Israel time, returned in UTC.
- Dietary groups are at most adults + children → `422 validation_error` with `details.field`.
- Delivery needs a street address, and its `delivery_city` must be in an active zone (`422 city_not_served`). The fee is live while draft and frozen at submit.
- A customer without a profile → `409 profile_required`.
- Someone else's order → `404`.
- A non-draft → `409 invalid_transition`.

## Change proposals (OPEN #6)

Owner, on an order awaiting approval:

| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/orders/{id}/proposals` | Newest first |
| POST | `/api/admin/orders/{id}/proposals` | `{items: [{dish_id, quantity}], note}` is the full wanted item list; the server derives the changes. Dishes and quantities only (no custom prices). `409 proposal_pending` if one is open; `422 no_changes`, `dish_unavailable`, `below_minimum` |
| POST | `/api/admin/orders/{id}/proposals/{pid}/cancel` | |

While a proposal is open, owner approve or reject returns `409 proposal_pending`.

Customer (owner of the order):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/orders/{id}/proposals` | Newest first |
| POST | `/api/orders/{id}/proposals/{pid}/accept` | Applies the frozen lines and approves the order in one transaction, only if `order.version == base_order_version`; otherwise the proposal expires (`409 proposal_expired`) |
| POST | `/api/orders/{id}/proposals/{pid}/decline` | `{note}`. The order stays awaiting the owner's decision |

A closed proposal returns `409 proposal_not_pending`. Withdrawing the order expires an open proposal.

## AI assistant (Phase 4)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/orders/{id}/chat` | `{message}` → `{reply, proposals:[...]}` |
| POST | `/api/orders/{id}/proposals/{pid}/accept` | Same endpoint as owner proposals (above); assistant proposals use `proposed_by = assistant` |
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
| GET/POST/PATCH/DELETE | `/api/admin/delivery-zones` `{name, fee, cities[], is_active}`. `cities` is a full replacement; a city already in another zone gives `409 city_taken` with `{city, zone}` |
| GET/POST/PATCH/DELETE | `/api/admin/time-slots` |
| GET/POST/DELETE | `/api/admin/blocked-dates` |
| GET | `/api/admin/orders?status=` · GET `/api/admin/orders/{id}` |
| POST | `/api/admin/orders/{id}/approve` · `/api/admin/orders/{id}/reject` `{note}` |

## Order status transitions

| Transition | Endpoint | Allowed actor |
|---|---|---|
| draft → pending_approval | `POST /api/orders/{id}/submit` | Order's customer |
| pending_approval → draft | `POST /api/orders/{id}/withdraw` | Order's customer |
| pending_approval → approved | `POST /api/admin/orders/{id}/approve` | Owner |
| pending_approval → rejected | `POST /api/admin/orders/{id}/reject` | Owner |

Any other transition → `409 invalid_transition`. The AI agent has no tool that triggers these.
