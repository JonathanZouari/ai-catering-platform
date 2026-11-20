# Preliminary Database Schema (PostgreSQL / Supabase)

Status: **Draft v0.1** — not yet migrated. First migration is planned for Phase 2.

Conventions **[RECOMMENDATION]**: `uuid` PKs (`gen_random_uuid()`), `timestamptz` `created_at`/`updated_at`, money as `numeric(10,2)`, enums as Postgres enum types, snake_case, RLS enabled on every table. Every uuid `id` has `DEFAULT gen_random_uuid()` in Postgres. Every foreign key is covered by an index, a primary key or a UNIQUE. `json` columns are `jsonb` in Postgres.

## Enums

| Enum | Values | Source |
|---|---|---|
| `pricing_unit` | `per_guest`, `per_tray`, `per_weight`, `per_item` | Decision 6 |
| `kashrut_class` | `meat`, `dairy`, `pareve` | Decision 9 |
| `fulfillment_type` | `pickup`, `delivery` | Decision 8 |
| `order_status` | `draft`, `pending_approval`, `approved`, `rejected` | Spec §10 (preliminary) |
| `proposal_status` | `pending`, `approved`, `rejected`, `expired`, `failed` | AI design |
| `allergen_status` | `contains`, `free`, `unknown` | Decision 9 — unknown ≠ free |

## Tables

### customers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| auth_user_id | uuid null unique | FK `auth.users` if accounts are chosen **[OPEN #1]** |
| full_name | text not null | |
| email | text null | |
| phone | text null | |
| created_at, updated_at | timestamptz | |

### events
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK → customers, not null | index; the only place an order's customer is stored |
| event_type | text not null | Private event label; list configurable **[RECOMMENDATION]** |
| event_date | date not null | |
| adults | int not null ≥ 0 | |
| children | int not null ≥ 0 | |
| vegetarian_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| vegan_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| restricted_guests | int not null ≥ 0 | |
| dietary_notes | text null | Free text, shown to owner; never parsed into safety claims |
| CHECK | `adults + children > 0` | |

### dish_categories
`id` uuid PK · `name` text not null unique · `sort_order` int not null default 0 · `is_active` bool default true

### dishes
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| category_id | uuid FK → dish_categories not null | index |
| name | text not null | |
| description | text null | |
| image_path | text null | Supabase Storage object path |
| pricing_unit | pricing_unit not null | |
| unit_price | numeric(10,2) not null CHECK ≥ 0 | |
| unit_label | text null | e.g., tray size / weight unit text **[OPEN #18]** |
| currency | char(3) not null default from config | **[OPEN #17]** |
| min_quantity | numeric(10,2) null | **[OPEN #15]** |
| is_available | bool not null default true | |
| created_at, updated_at | timestamptz | |

### dish_dietary (1:1 with dishes)
`dish_id` uuid PK/FK → dishes · `kashrut_class` kashrut_class **null** (null = not provided) · `is_vegetarian` bool null · `is_vegan` bool null · `verified_at` timestamptz null

Null booleans mean **unknown** and must be presented as unknown, never as "no"/"yes".

### allergens
`id` smallint PK · `name` text unique (list maintained by owner)

### dish_allergens
`dish_id` FK · `allergen_id` FK · `status` allergen_status not null · PK(`dish_id`,`allergen_id`)
A missing row = **unknown**.

### delivery_zones
`id` uuid PK · `name` text not null · `fee` numeric(10,2) not null ≥ 0 · `definition` jsonb not null (shape depends on **[OPEN #19]**) · `is_active` bool

### time_slots
`id` uuid PK · `fulfillment_type` fulfillment_type · `weekday` smallint 0–6 null · `start_time` time · `end_time` time · `capacity` int null **[OPEN #5]** (**not enforced**: there is no reservations table yet; also stored as a SQL column comment) · `is_active` bool · CHECK `end_time > start_time`

### blocked_dates
`id` uuid PK · `date` date unique · `reason` text null

### orders
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| event_id | uuid FK not null unique | The customer is `events.customer_id` via this column; there is no `orders.customer_id` |
| status | order_status not null default `draft` | index |
| version | int not null default 1 | Incremented on every mutation; optimistic locking for proposals |
| fulfillment_type | fulfillment_type not null | |
| requested_at | timestamptz not null | Requested pickup/delivery time |
| delivery_address | text null | CHECK: required when `delivery` |
| delivery_zone_id | uuid FK null | index |
| subtotal, delivery_fee, total | numeric(10,2) null | Computed by backend; frozen at submission |
| submitted_at, decided_at | timestamptz null | |
| decision_note | text null | Owner's note on approve/reject |
| created_at, updated_at | timestamptz | |

### order_items
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| dish_id | uuid FK not null | index |
| quantity | numeric(10,2) not null CHECK > 0 | |
| UNIQUE | (`order_id`, `dish_id`) | |
| snapshot_name | text null | **Price snapshot** — filled on submission |
| snapshot_pricing_unit | pricing_unit null | |
| snapshot_unit_price | numeric(10,2) null | |
| snapshot_line_total | numeric(10,2) null | |

While `draft`, prices are read live from `dishes`; on `pending_approval` the snapshot columns become authoritative.

### ai_conversations
`id` uuid PK · `order_id` FK not null · `created_at` · index on `order_id` · UNIQUE (`id`, `order_id`), the target of the composite FK from `ai_change_proposals`

### ai_messages
`id` uuid PK · `conversation_id` FK · `role` text CHECK in (`user`,`assistant`,`tool`) · `content` jsonb · `created_at`

### ai_change_proposals
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| conversation_id | uuid null | Composite FK (`conversation_id`, `order_id`) → `ai_conversations` (`id`, `order_id`): the conversation must belong to the same order. Not checked when NULL. Indexed. |
| base_order_version | int not null | Must equal `orders.version` at execution |
| changes | jsonb not null | Validated list of typed operations |
| price_before, price_after | numeric(10,2) not null | Computed by backend at proposal time |
| status | proposal_status not null default `pending` | |
| created_at, decided_at, executed_at | timestamptz | `executed_at` set once → idempotency |
| PARTIAL UNIQUE | one `pending` per order? **[RECOMMENDATION]** — simplifies UI | |

## Status transitions **[RECOMMENDATION]**

| From | To | Actor |
|---|---|---|
| draft | pending_approval | Customer (owner of the order's event) |
| pending_approval | approved | Owner |
| pending_approval | rejected | Owner |

Proposals may only execute while order is `draft`.

## Migrations

`database/migrations/0001_schema_review_fixes.sql` upgrades a database created before the review fixes. It is applied by hand in the Supabase dashboard SQL editor (dev first, then prod). Run these read-only checks first; every count must be 0:

```sql
SELECT count(*) FROM orders o JOIN events e ON e.id = o.event_id
WHERE o.customer_id IS DISTINCT FROM e.customer_id;
SELECT count(*) FROM orders WHERE event_id IS NULL;
SELECT count(*) FROM events WHERE customer_id IS NULL;
SELECT count(*) FROM ai_change_proposals p JOIN ai_conversations c ON c.id = p.conversation_id
WHERE c.order_id <> p.order_id;
-- Informational: FK constraint names currently on ai_change_proposals
SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid = 'public.ai_change_proposals'::regclass AND contype = 'f' ORDER BY conname;
```

## Business rules storage

Quantity rules (Decision 5) will live in a `quantity_rules` table once formulas are known **[OPEN #3]**. Shape intentionally not designed yet.
