# Preliminary Database Schema (PostgreSQL / Supabase)

Status: **Draft v0.2** — not yet migrated. First migration is planned for Phase 3.

Conventions **[RECOMMENDATION]**: `uuid` PKs (`gen_random_uuid()`), `timestamptz` `created_at`/`updated_at`, money as `numeric(10,2)`, enums as Postgres enum types, snake_case, RLS enabled on every table.

**Tenancy (ADR 0005):** every table below `caterer_users` has a non-null `caterer_id` FK → `caterers`, indexed, unless the table is marked *scoped through parent*. Unique constraints include `caterer_id`. Tables marked *platform* are shared across caterers. Hebrew text is stored in the existing `name`/`description` columns; there are no per-language columns.

## Enums

| Enum | Values | Source |
|---|---|---|
| `pricing_unit` | `per_guest`, `per_tray`, `per_weight`, `per_item` | Decision 6 |
| `kashrut_class` | `meat`, `dairy`, `pareve` | Decision 9 |
| `fulfillment_type` | `pickup`, `delivery` | Decision 8 |
| `order_status` | `draft`, `pending_approval`, `approved`, `rejected` | Spec §10 (preliminary) |
| `proposal_status` | `pending`, `approved`, `rejected`, `expired`, `failed` | AI design |
| `allergen_status` | `contains`, `free`, `unknown` | Decision 9 — unknown ≠ free |
| `kashrut_mixing_rule` | `block`, `warn` | Decision 17 |

## Tables

### caterers *(tenant root)*
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| slug | text not null unique | Used in `/c/{slug}/`; lowercase latin, digits, hyphens |
| name | text not null | Hebrew business name |
| logo_path | text null | Supabase Storage object path |
| brand_color | text null | Hex color; validated for contrast in the UI |
| contact_phone | text null | Shown to customers |
| kashrut_status | text null | Free text shown to customers, e.g., certifying body. Null = not provided |
| kashrut_certificate_path | text null | Supabase Storage object path |
| kashrut_mixing_rule | kashrut_mixing_rule not null default `warn` | Applies to meat + dairy in one order |
| currency | char(3) not null default `ILS` | |
| ai_monthly_message_limit | int null | Per-caterer chat cap |
| is_active | bool not null default true | Inactive caterer's link shows "unavailable" |
| created_at, updated_at | timestamptz | |

### caterer_users
`id` uuid PK · `caterer_id` FK not null · `auth_user_id` uuid not null FK `auth.users` · `created_at` · UNIQUE(`auth_user_id`)

One login belongs to exactly one caterer in the MVP.

### customers
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| caterer_id | uuid FK not null | Customers are per caterer (ADR 0006) |
| full_name | text not null | |
| phone | text not null | Contact only; not verified |
| email | text null | |
| created_at, updated_at | timestamptz | |

### events
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| caterer_id | uuid FK not null | index |
| customer_id | uuid FK → customers, not null | |
| event_type | text not null | Private event label; list configurable **[RECOMMENDATION]** |
| event_date | date not null | |
| adults | int not null ≥ 0 | |
| children | int not null ≥ 0 | |
| vegetarian_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| vegan_guests | int not null ≥ 0 | Subset semantics **[OPEN #4]** |
| restricted_guests | int not null ≥ 0 | |
| dietary_notes | text null | Free text, shown to the caterer; never parsed into safety claims |
| CHECK | `adults + children > 0` | |

### dish_categories
`id` uuid PK · `caterer_id` FK · `name` text not null · `sort_order` int not null default 0 · `is_active` bool default true · UNIQUE(`caterer_id`,`name`)

### dishes
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| caterer_id | uuid FK not null | index |
| category_id | uuid FK → dish_categories not null | index; must belong to the same caterer |
| name | text not null | |
| description | text null | |
| image_path | text null | Supabase Storage object path |
| pricing_unit | pricing_unit not null | |
| unit_price | numeric(10,2) not null CHECK ≥ 0 | |
| unit_label | text null | e.g., tray size / weight unit text **[OPEN #18]** |
| calories_per_portion | int null CHECK ≥ 0 | Null = unknown. Entered by the caterer; never estimated by the AI |
| portion_description | text null | What one portion means, e.g., "100 גרם" |
| min_quantity | numeric(10,2) null | **[OPEN #15]** |
| is_available | bool not null default true | |
| created_at, updated_at | timestamptz | |

### dish_dietary (1:1 with dishes, *scoped through parent*)
`dish_id` uuid PK/FK → dishes · `kashrut_class` kashrut_class **null** (null = not provided) · `is_vegetarian` bool null · `is_vegan` bool null · `verified_at` timestamptz null

Null booleans mean **unknown** and must be presented as unknown, never as "no"/"yes".

### allergens *(platform)*
`id` smallint PK · `name` text unique (Hebrew; one shared list maintained by the platform, so the AI and filters mean the same thing at every caterer)

### dish_allergens *(scoped through parent)*
`dish_id` FK · `allergen_id` FK · `status` allergen_status not null · PK(`dish_id`,`allergen_id`)
A missing row = **unknown**.

### delivery_zones
`id` uuid PK · `caterer_id` FK · `name` text not null · `fee` numeric(10,2) not null ≥ 0 · `definition` jsonb not null (shape depends on **[OPEN #19]**) · `is_active` bool

### time_slots
`id` uuid PK · `caterer_id` FK · `fulfillment_type` fulfillment_type · `weekday` smallint 0–6 null · `start_time` time · `end_time` time · `capacity` int null **[OPEN #5]** · `is_active` bool · CHECK `end_time > start_time`

### blocked_dates
`id` uuid PK · `caterer_id` FK · `date` date · `reason` text null · UNIQUE(`caterer_id`,`date`)

### orders
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| caterer_id | uuid FK not null | index |
| access_token_hash | text not null unique | SHA-256 of the private link token (ADR 0006) |
| customer_id | uuid FK not null | index |
| event_id | uuid FK not null unique | |
| status | order_status not null default `draft` | index |
| version | int not null default 1 | Incremented on every mutation; optimistic locking for proposals |
| fulfillment_type | fulfillment_type not null | |
| requested_at | timestamptz not null | Requested pickup/delivery time |
| delivery_address | text null | CHECK: required when `delivery` |
| delivery_zone_id | uuid FK null | |
| subtotal, delivery_fee, total | numeric(10,2) null | Computed by backend; frozen at submission |
| submitted_at, decided_at | timestamptz null | |
| kashrut_warning_acknowledged | bool not null default false | Customer accepted a meat + dairy warning, when the rule is `warn` |
| decision_note | text null | Caterer's note on approve/reject |
| created_at, updated_at | timestamptz | |

### order_items *(scoped through parent)*
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| dish_id | uuid FK not null | Must belong to the order's caterer |
| quantity | numeric(10,2) not null CHECK > 0 | |
| UNIQUE | (`order_id`, `dish_id`) | |
| snapshot_name | text null | **Price snapshot** — filled on submission |
| snapshot_pricing_unit | pricing_unit null | |
| snapshot_unit_price | numeric(10,2) null | |
| snapshot_line_total | numeric(10,2) null | |

While `draft`, prices are read live from `dishes`; on `pending_approval` the snapshot columns become authoritative.

### ai_conversations *(scoped through parent)*
`id` uuid PK · `order_id` FK not null · `created_at` · index on `order_id`

### ai_messages *(scoped through parent)*
`id` uuid PK · `conversation_id` FK · `role` text CHECK in (`user`,`assistant`,`tool`) · `content` jsonb · `created_at`

### ai_change_proposals *(scoped through parent)*
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| order_id | uuid FK not null | index |
| conversation_id | uuid FK null | |
| base_order_version | int not null | Must equal `orders.version` at execution |
| changes | jsonb not null | Validated list of typed operations |
| price_before, price_after | numeric(10,2) not null | Computed by backend at proposal time |
| status | proposal_status not null default `pending` | |
| created_at, decided_at, executed_at | timestamptz | `executed_at` set once → idempotency |
| PARTIAL UNIQUE | one `pending` per order? **[RECOMMENDATION]** — simplifies UI | |

## Status transitions **[RECOMMENDATION]**

| From | To | Actor |
|---|---|---|
| draft | pending_approval | Holder of the order's private link |
| pending_approval | approved | Caterer of that order |
| pending_approval | rejected | Caterer of that order |

Proposals may only execute while order is `draft`.

## Business rules storage

Quantity rules (Decision 5) live in `quantity_rules`. A row with `caterer_id` null is a platform default; a row with a `caterer_id` overrides it for that caterer. Default values are **[OPEN #3]**, and the final shape is settled in Phase 5.
