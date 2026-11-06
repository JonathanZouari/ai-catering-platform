# Database Schema (Supabase Postgres)

Status: **v0.3** — live in the `ai-catering-dev` Supabase project since 2026-11-05.
v0.3 (2026-11-06) drops the SQLite compatibility of v0.2: the database is Supabase Postgres in every environment (ADR-0002).
The SQL source of truth is `supabase/migrations/`; synthetic demo data is in `supabase/seed.sql`. This document describes it.
Diagrams: [`ERD.md`](ERD.md).

## Conventions

One engine, Supabase Postgres. Postgres features are used where they protect the data (enum types, `jsonb`, partial indexes, triggers, RLS).

| Concern | Rule |
|---|---|
| Schema source | SQL migrations in `supabase/migrations/`, created with `supabase migration new` and applied with `supabase db push`. Never edit a migration that has been applied; add a new one |
| Primary keys | `uuid`, default `gen_random_uuid()` (the app may also supply its own). `staff_users.id` is the Supabase Auth user id |
| Timestamps | `created_at`, `updated_at` (`timestamptz`, default `now()`) on every mutable table. A trigger (`private.set_updated_at`) sets `updated_at` on every update |
| Money | Integer **agorot**, columns named `*_agorot` (₪85.50 → `8550`). Currency is ILS, held in `settings` |
| Quantities | Integer **thousandths of the dish unit**, columns named `*_milli` (3 trays → `3000`; 1.5 kg of a per-100 g dish = 15 units → `15000`) |
| Percentages | Integer basis points, columns named `*_bp` (18% → `1800`) |
| Enums | Postgres enum types (listed below). Add a value with `alter type … add value`; removing one needs a new type |
| JSON | `jsonb`, validated by Pydantic in the backend before it is written |
| Booleans for facts | Nullable where "not provided" is possible: **null = unknown**, never shown as yes or no |
| Foreign keys | Always enforced. Every foreign-key column has an index |
| Authorization | Row Level Security on every table for browser traffic (see "Access rules"). The backend's direct connection is privileged and enforces the business rules itself |
| Names | snake_case, plural table names |

### Price arithmetic (deterministic, backend only)

`line_total_agorot = round_half_up(quantity_milli × price_agorot / 1000)`, computed once per line in integers, rounded half up to the agora. `subtotal_agorot` is the exact sum of line totals and `total_agorot` = subtotal + delivery fee, with no further rounding, so the lines always add up to the total (decision #14).

## Enum types

| Name | Values | Used in |
|---|---|---|
| dish_unit | `tray`, `100g`, `item`, `guest` | `dishes.unit`, `order_items.snapshot_unit` |
| kashrut | `meat`, `dairy`, `pareve` (null = unknown) | `dishes.kashrut`, `order_items.snapshot_kashrut` |
| allergen_status | `contains`, `may_contain`, `free` (no row = unknown) | `dish_allergens.status` |
| fulfillment | `pickup`, `delivery` | `time_slots`, `orders` |
| order_status | `draft`, `pending_approval`, `approved`, `rejected`, `cancelled`, `completed` | `orders.status`, `order_events.from_status`, `order_events.to_status` |
| actor_type | `customer`, `staff`, `system` | `order_events` |
| message_role | `user`, `assistant`, `tool` | `ai_messages` |
| proposal_status | `pending`, `approved`, `rejected`, `expired`, `failed` | `ai_change_proposals` |

## Tables

### Settings and staff

#### settings (exactly one row)
| Column | Type | Notes |
|---|---|---|
| id | int PK | CHECK `id = 1` |
| default_max_guests_per_day | int not null CHECK > 0 | Kitchen capacity when no `calendar_overrides` row exists |
| min_lead_days | int not null CHECK ≥ 0 | Earliest bookable date = today + this |
| vat_rate_bp | int not null CHECK ≥ 0 | Current VAT rate; prices are VAT-inclusive |
| currency | text not null default `'ILS'` | |
| updated_at | timestamptz | |

#### staff_users
| Column | Type | Notes |
|---|---|---|
| id | uuid PK, FK → `auth.users` ON DELETE CASCADE | The staff member's Supabase Auth login. Passwords live in Supabase Auth, never in this table |
| email | text not null unique | Read-only copy of the Auth email, for staff lists. Filled from `auth.users` by a trigger on every insert/update, and updated when the email changes in Supabase Auth |
| full_name | text not null | |
| is_active | bool not null default true | |
| created_at, updated_at | timestamp | |

### Menu

#### categories
`id` uuid PK · `name` text not null unique · `sort_order` int not null default 0 · `is_active` bool not null default true · timestamps

#### dishes
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| category_id | uuid FK → categories, not null | index |
| name | text not null | |
| description | text null | |
| image_path | text null | Storage object path (local disk in dev, Supabase Storage in prod) |
| unit | dish_unit not null | One unit and one price per dish; a different size is a separate dish. Weight is always priced per 100 g (decision #18) |
| unit_label | text null | Customer-facing size text, e.g. "מגש ל-10 סועדים" |
| price_agorot | int not null CHECK ≥ 0 | VAT-inclusive |
| qty_per_adult_milli | int null CHECK ≥ 0 | Recommended amount per adult. Null = no recommendation for this dish **[OPEN #3 values]** |
| qty_per_child_milli | int null CHECK ≥ 0 | |
| qty_step_milli | int not null default 1000 CHECK > 0 | Rounding step for recommendations and the quantity stepper (e.g. `5000` = 500 g for a `100g` dish) |
| qty_min_milli | int null CHECK > 0 | Minimum orderable quantity **[OPEN #15]** |
| kashrut | kashrut null | null = unknown |
| is_vegetarian | bool null | null = unknown |
| is_vegan | bool null | null = unknown. CHECK: not (`is_vegan` = true and `is_vegetarian` = false) |
| allergens_verified_by | uuid FK → staff_users null | Who last confirmed this dish's allergen rows |
| allergens_verified_at | timestamp null | |
| is_available | bool not null default true | |
| sort_order | int not null default 0 | |
| created_at, updated_at | timestamp | |

#### allergens
`id` uuid PK · `name` text not null unique (Hebrew) · `sort_order` int not null default 0. List maintained by the owner.

#### dish_allergens
| Column | Type | Notes |
|---|---|---|
| dish_id | uuid FK → dishes | PK part, ON DELETE CASCADE |
| allergen_id | uuid FK → allergens | PK part |
| status | allergen_status not null | |

A missing row means **unknown** and must be presented as unknown, never as allergen-free.

### Delivery and availability

#### delivery_zones
`id` uuid PK · `name` text not null unique · `fee_agorot` int not null CHECK ≥ 0 · `is_active` bool not null default true · timestamps

#### zone_cities
`city` text PK (normalized Hebrew city name) · `zone_id` uuid FK → delivery_zones not null (index)

The customer picks a city from this list; the city decides the zone and fee. No geocoding.

#### time_slots
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| fulfillment | fulfillment not null | |
| weekday | int null CHECK 0–6 | null = every day |
| start_time, end_time | time not null | CHECK `end_time > start_time` |
| is_active | bool not null default true | |

Slots decide **when** pickup/delivery happens. They carry no capacity: capacity is guests per day (below).

#### calendar_overrides
| Column | Type | Notes |
|---|---|---|
| date | date PK | |
| max_guests | int null CHECK ≥ 0 | Overrides `settings.default_max_guests_per_day` for this date |
| is_blocked | bool not null default false | A blocked day takes no orders (replaces v0.1 `blocked_dates`) |
| reason | text null | Internal note |

### Customers and orders

#### customers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| full_name | text not null | |
| phone | text not null unique | Normalized (digits only). One phone = one customer: a returning customer is matched by phone and their name/email updated |
| email | text null | |
| auth_user_id | uuid null unique, FK → `auth.users` ON DELETE SET NULL | The customer's Supabase Auth login, if they have one. How a new login gets linked to an existing customer is still open **[OPEN #1]** |
| created_at, updated_at | timestamp | |

#### orders
Event details live on the order (v0.1 `events` was always 1:1 and is merged in).

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK → customers not null | index |
| access_token_hash | text not null unique | SHA-256 of the secret in the customer's private order link. The plain token is never stored |
| status | order_status not null default `'draft'` | Index (`status`, `event_date`) |
| version | int not null default 1 | Incremented on every mutation; AI proposals execute only against a matching version |
| event_type | text not null | From the configured list of private event types |
| event_date | date not null | |
| time_slot_id | uuid FK → time_slots null | |
| slot_start, slot_end | time null | Copied from the slot, so later slot edits don't change the order |
| adults | int not null CHECK ≥ 1 | |
| children | int not null default 0 CHECK ≥ 0 | |
| vegetarian, vegan, restricted | int not null default 0 CHECK ≥ 0 | **Subsets** of adults + children, mutually exclusive (a vegan is not also counted as vegetarian). CHECK `vegetarian + vegan + restricted ≤ adults + children` |
| dietary_notes | text null | Free text for the owner; never parsed into safety claims |
| fulfillment | fulfillment not null | |
| city | text null | FK → zone_cities.city |
| delivery_address | text null | CHECK: `city` and `delivery_address` not null when `fulfillment = 'delivery'` |
| delivery_zone_id | uuid FK → delivery_zones null | |
| delivery_fee_agorot | int null | Frozen at submission |
| subtotal_agorot | int null | Sum of line totals, frozen at submission |
| total_agorot | int null | Subtotal + delivery fee, frozen at submission (VAT-inclusive) |
| vat_rate_bp | int null | Copied from `settings` at submission |
| vat_agorot | int null | VAT contained in the total: `round(total × rate / (10000 + rate))` |
| submitted_at | timestamp null | |
| created_at, updated_at | timestamp | |

While `draft`, totals are computed live from `dishes`. On submission (`draft → pending_approval`) every `*_agorot` field and the `order_items` snapshots are written in the same transaction and become authoritative.

#### order_items
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK → orders not null | index, ON DELETE CASCADE |
| dish_id | uuid FK → dishes not null | |
| quantity_milli | int not null CHECK > 0 | |
| UNIQUE | (`order_id`, `dish_id`) | |
| snapshot_name | text null | Filled on submission |
| snapshot_unit | dish_unit null | |
| snapshot_kashrut | kashrut null | Copied at submission so the meat/dairy warning on a submitted quote survives later dish edits |
| snapshot_price_agorot | int null | |
| line_total_agorot | int null | |

#### order_events (status history and audit)
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK → orders not null | index (`order_id`, `created_at`) |
| from_status | order_status null | null for the creation event |
| to_status | order_status not null | |
| actor_type | actor_type not null | |
| staff_user_id | uuid FK → staff_users null | Set when `actor_type = 'staff'` |
| note | text null | Owner's approve/reject note, cancellation reason, etc. |
| created_at | timestamp not null | |

Replaces v0.1 `decided_at` / `decision_note` columns. The current status is still on `orders.status`; this table is the history.

### AI assistant

#### ai_conversations
`id` uuid PK · `order_id` uuid FK → orders not null (index) · `created_at`

#### ai_messages
`id` uuid PK · `conversation_id` uuid FK → ai_conversations not null (index) · `role` message_role not null · `content` jsonb not null · `created_at`

#### ai_change_proposals
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK → orders not null | index |
| conversation_id | uuid FK → ai_conversations null | |
| base_order_version | int not null | Must equal `orders.version` at execution |
| changes | jsonb not null | Validated list of typed operations (`AI_AGENT_DESIGN.md`) |
| price_before_agorot, price_after_agorot | int not null | Computed by the backend at proposal time |
| status | proposal_status not null default `'pending'` | |
| created_at, decided_at, executed_at | timestamp | `executed_at` is set once, which makes execution idempotent |
| PARTIAL UNIQUE | (`order_id`) WHERE `status = 'pending'` | At most one pending proposal per order |

## Order status transitions

| From | To | Actor | Allowed in MVP |
|---|---|---|---|
| draft | pending_approval | Customer | Yes |
| pending_approval | approved | Staff | Yes |
| pending_approval | rejected | Staff | Yes |
| any open status | cancelled | Customer / Staff | Only once **[OPEN #7]** is decided |
| approved | completed | Staff / System | Yes (after the event date) |

The schema accepts all six statuses; the backend allows only the transitions above. Every transition writes an `order_events` row in the same transaction. AI proposals may only execute while the order is `draft`.

## Rules enforced by the backend

| Rule | Where |
|---|---|
| **Daily guest capacity**: for `event_date`, limit = `calendar_overrides.max_guests` if set, else `settings.default_max_guests_per_day`. Sum `adults + children` over orders in `pending_approval` or `approved` on that date; submission fails if the new order would exceed the limit. Blocked dates and `min_lead_days` are checked first | Submission service, inside the submit transaction. Take a transaction-scoped advisory lock on the date (`pg_advisory_xact_lock`) so two concurrent submissions can't both take the last places |
| Price and quantity calculation, price snapshot at submission | Pricing service (ADR-0003) |
| Proposal execution: version match, single execution | Proposal service (`AI_AGENT_DESIGN.md`) |
| **Meat/dairy mix warning**: mixing is allowed. If an order has both a `meat` and a `dairy` dish, the customer sees a warning and the owner sees a flag on the order. Computed from the items (from `snapshot_kashrut` once submitted); no stored flag. The AI must say so when a suggestion creates a mix | Pricing/order service, admin order view, AI tools |
| **AI chat retention**: delete `ai_messages` (and empty `ai_conversations`) **90 days after `event_date`**. `ai_change_proposals` stay with the order as the audit trail. The chat shows a short notice that messages are kept for 90 days after the event | Scheduled daily job, chat UI |

## Access rules (RLS), storage and realtime

RLS is on for every table. Browser requests use the publishable key and run as `anon` (not logged in) or `authenticated`. Two helper functions in the non-exposed `private` schema decide who the caller is: `private.is_staff()` (an active `staff_users` row for `auth.uid()`) and `private.my_customer_id()`. Roles are never taken from `user_metadata`.

| Who | Can read | Can change |
|---|---|---|
| Visitor (`anon`) | Menu: active categories, available dishes, allergens, active delivery zones and cities, active time slots, settings | Nothing |
| Customer | The menu, plus their own `customers` row, orders, order lines, order history, AI chats and suggestions | Their own `customers` row only. Orders are created and changed through the backend (ADR-0003) |
| Staff | Everything | Everything |
| Backend (direct connection) | Everything (bypasses RLS) | Everything, following the backend rules above |

`calendar_overrides` is staff-only because `reason` is an internal note; the backend tells customers which dates are free.

**Storage:** public bucket `dish-images` (5 MB max; JPEG, PNG, WEBP). Anyone can view an image by its URL; only staff can upload, replace (upsert) or delete. `dishes.image_path` holds the object path inside the bucket, e.g. `dishes/<dish id>/<timestamp>.webp`.

**Realtime:** `orders` and `order_events` are in the `supabase_realtime` publication. Subscribers receive only the rows their read rules allow: staff get every order, a customer only their own.

## Changes in v0.3 (2026-11-06)

- SQLite dropped. Schema source moved from Alembic to `supabase/migrations/`.
- Text + CHECK replaced by enum types. Four columns that had no check now have one (`order_events.from_status`, `to_status`, `order_items.snapshot_kashrut`, `snapshot_unit`).
- `json` → `jsonb`; `updated_at` maintained by a trigger.
- Login moved to Supabase Auth: `staff_users.password_hash` and `last_login_at` removed (Auth keeps `last_sign_in_at`), `staff_users.email` follows the Auth email, `staff_users.id` and `customers.auth_user_id` reference `auth.users`.
- RLS became the access control for browser traffic; `dish-images` bucket and Realtime added.

## Changes in v0.2 (from v0.1)

- **Removed:** `events` (merged into `orders`), `dish_dietary` (merged into `dishes`), `blocked_dates` (now `calendar_overrides.is_blocked`), placeholder `quantity_rules` (now columns on `dishes`).
- **Added:** `settings`, `staff_users`, `zone_cities`, `calendar_overrides`, `order_events`.
- Money moved from `numeric(10,2)` to integer agorot; quantities to integer thousandths; Postgres enums and `jsonb` replaced by portable types.
- `allergen_status` gained `may_contain`; `order_status` gained `cancelled` and `completed`.
- `time_slots.capacity` removed: capacity is guests per day.
- Weight unit is `100g` instead of `kg`; `customers.phone` is unique; `order_items.snapshot_kashrut` added.

## Still open

| Question | Affects |
|---|---|
| Which kashrut certification(s), and shown per dish or business-wide? **[OPEN #9, rest]** | Possibly a `certification` field on `settings` or `dishes` |
| Recommended-amount values per dish **[OPEN #3]** | Data in `dishes.qty_*`, not schema |
