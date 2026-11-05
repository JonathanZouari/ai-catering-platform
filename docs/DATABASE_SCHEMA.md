# Preliminary Database Schema (PostgreSQL / Supabase)

Status: **Draft v0.1** — not yet migrated. First migration is planned for Phase 2.

Conventions **[RECOMMENDATION]**: `uuid` PKs (`gen_random_uuid()`), `timestamptz` `created_at`/`updated_at`, money as `numeric(10,2)`, enums as Postgres enum types, snake_case, RLS enabled on every table.

## Enums

| Enum | Values | Source |
|---|---|---|
| `pricing_unit` | `per_guest`, `per_tray`, `per_weight`, `per_item` | Decision 6 |
| `kashrut_class` | `meat`, `dairy`, `pareve` | Decision 9: only `meat` and `pareve` are allowed (check constraint, migration 0011); `dairy` stays in the type because Postgres can't drop an enum value |
| `fulfillment_type` | `pickup`, `delivery` | Decision 8 |
| `order_status` | `draft`, `pending_approval`, `approved`, `rejected` | Spec §10 (preliminary) |
| `proposal_status` | `pending`, `approved`, `rejected`, `expired`, `failed` | AI design |
| `allergen_status` | `contains`, `free`, `unknown` | Decision 9 — unknown ≠ free |

## Tables

### customers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| auth_user_id | uuid null unique | FK `auth.users` (ADR 0005); null for customers created without an account |
| full_name | text not null | |
| email | text null | |
| phone | text null | |
| created_at, updated_at | timestamptz | |

### events
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK → customers, not null | |
| event_type | text not null | Private event label; list configurable **[RECOMMENDATION]** |
| event_date | date not null | |
| adults | int not null ≥ 0 | |
| children | int not null ≥ 0 | |
| vegetarian_guests | int not null ≥ 0 | Subset of adults + children (decided, #4) |
| vegan_guests | int not null ≥ 0 | Subset of adults + children; vegan ⊂ vegetarian still **[OPEN #4]** |
| restricted_guests | int not null ≥ 0 | Subset of adults + children |
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
| unit_label | text null | e.g., tray size; weight prices are per kg (#18 decided) |
| currency | char(3) not null default `ILS` | ILS only (#17 decided) |
| min_quantity | numeric(10,2) null | Per-dish minimum; the only minimum (#15 decided) |
| serves_adults | numeric(10,2) null > 0 | Adults one unit serves, for recommendations (#3); null = no advice |
| is_available | bool not null default true | |
| contains_alcohol | bool not null default false | Sold to 18+ only (#11, migration 0012) |
| created_at, updated_at | timestamptz | |

### dish_dietary (1:1 with dishes)
`dish_id` uuid PK/FK → dishes · `kashrut_class` kashrut_class **not null, default `pareve`**, check in (`meat`, `pareve`) (#9, migration 0011) · `is_vegetarian` bool null · `is_vegan` bool null · `verified_at` timestamptz null

Null booleans mean **unknown** and must be presented as unknown, never as "no"/"yes".

### allergens
`id` smallint PK · `name` text unique (list maintained by owner)

### dish_allergens
`dish_id` FK · `allergen_id` FK · `status` allergen_status not null · PK(`dish_id`,`allergen_id`)
A missing row = **unknown**.

### delivery_zones
`id` uuid PK · `name` text not null unique · `fee` numeric(10,2) not null ≥ 0 · `is_active` bool (OPEN #19 decided: zones are city lists)

### delivery_zone_cities
`city` text PK (normalized; a city belongs to at most one zone) · `zone_id` FK → delivery_zones, on delete cascade

### time_slots
`id` uuid PK · `fulfillment_type` fulfillment_type · `weekday` smallint 0–6 null · `start_time` time · `end_time` time · `capacity` int null (orders per slot per date, enforced at submission; null = unlimited) · `is_active` bool · CHECK `end_time > start_time`

### blocked_dates
`id` uuid PK · `date` date unique · `reason` text null

### orders
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK not null | index |
| event_id | uuid FK not null unique | |
| status | order_status not null default `draft` | index |
| version | int not null default 1 | Incremented on every mutation; optimistic locking for proposals |
| fulfillment_type | fulfillment_type not null | |
| slot_id | uuid FK → time_slots null | Chosen slot; on delete set null; capacity counted per slot per event date |
| requested_at | timestamptz not null | Requested pickup/delivery time |
| delivery_address | text null | CHECK: required when `delivery` |
| delivery_city | text null | A zone city, required for delivery |
| delivery_zone_id | uuid FK null | Zone whose fee was frozen at submission; on delete set null |
| subtotal, delivery_fee, total | numeric(10,2) null | Computed by backend; frozen at submission |
| submitted_at, decided_at | timestamptz null | |
| adult_confirmed_at | timestamptz null | When the customer confirmed 18+ at submission; set only for orders with alcohol, cleared on withdraw (#11) |
| decision_note | text null | Owner's note on approve/reject |
| created_at, updated_at | timestamptz | |

### order_items
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| dish_id | uuid FK not null | |
| quantity | numeric(10,2) not null CHECK > 0 | |
| UNIQUE | (`order_id`, `dish_id`) | |
| snapshot_name | text null | **Price snapshot** — filled on submission |
| snapshot_pricing_unit | pricing_unit null | |
| snapshot_unit_price | numeric(10,2) null | |
| snapshot_line_total | numeric(10,2) null | |

While `draft`, prices are read live from `dishes`; on `pending_approval` the snapshot columns become authoritative.

### ai_conversations (migration 0010)
`id` uuid PK · `order_id` FK not null, **unique** (one conversation per order), cascade · `created_at`

### ai_messages (migration 0010)
`id` bigint identity PK (keeps the order) · `conversation_id` FK cascade, indexed · `role` text CHECK in (`user`,`assistant`) · `content` jsonb (Claude API content blocks, incl. thinking and tool_use/tool_result; tool results are `user` messages, as the API sends them) · `customer_text` text null (the customer's own words; counted for the daily limit and shown in the chat) · `created_at`. Append-only.

### order_proposals
One table for both proposers (migration 0009, OPEN #6 decided): `owner` proposes on orders awaiting approval, and `assistant` (Phase 4) on drafts. It replaces the planned `ai_change_proposals`.

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null, cascade | index |
| proposed_by | text `owner` or `assistant` | |
| base_order_version | int not null | Must equal `orders.version` when accepted, else the proposal expires |
| changes | jsonb not null | `[{op: add_item, set_quantity or remove_item, dish_id, name, from_quantity, to_quantity}]` |
| lines | jsonb not null | Full proposed item list with frozen prices (existing dishes keep their frozen price, added dishes take the catalog price) |
| price_before, price_after | numeric(10,2) not null | `price_after` includes the order's delivery fee |
| note | text null | From the proposer, shown to the customer; becomes the decision note on accept |
| status | text: pending, accepted, declined, cancelled, expired | |
| customer_note | text null | Reason when declining |
| created_at, decided_at | timestamptz | |
| UNIQUE (order_id) WHERE status = 'pending' | | At most one open proposal per order |
| conversation_id, executed_at | | Added with the AI assistant in Phase 4 |

## Status transitions

| From | To | Actor |
|---|---|---|
| draft | pending_approval | Customer (owner of order) |
| pending_approval | draft | Customer, withdraw (OPEN #7) |
| pending_approval | approved | Owner, or customer accepting an owner proposal |
| pending_approval | rejected | Owner |

Owner proposals: on `pending_approval`. Accepting one moves the order to `approved` in the same transaction; declining leaves it `pending_approval`. Assistant proposals (Phase 4) apply to `draft`.

## Business rules storage

Quantity rules (OPEN #3, decided) need no rules table: `dishes.serves_adults` per dish plus `business_settings` (single row: `child_portion` 0.75, `lead_days` 3, and `assistant_daily_limit` 30 messages per customer in any 24 hours, migration 0010). See ERD.md for the formula.
