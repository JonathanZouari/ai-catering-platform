# Entity-Relationship Diagram

Status: matches migrations `0001`–`0010` and `backend/app/models/`. **Update this file in the same PR as every new migration.** Column-level notes and rationale live in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

Postgres types are shown. Local/test SQLite stores uuids as `char(32)` and enums as `varchar`. Every table has RLS enabled with no policies, because only the backend's privileged connection reads and writes (ADR 0002).

## Implemented

```mermaid
erDiagram
    dish_categories ||--o{ dishes : "groups"
    dishes ||--o| dish_dietary : "has (0..1)"
    dishes ||--o{ dish_allergens : "declares"
    allergens ||--o{ dish_allergens : "appears in"
    customers ||--o{ events : "plans"
    customers ||--o{ orders : "places"
    events ||--|| orders : "is ordered by"
    orders ||--o{ order_items : "contains"
    time_slots |o--o{ orders : "booked in"
    delivery_zones ||--o{ delivery_zone_cities : "covers"
    delivery_zones |o--o{ orders : "fee frozen from"
    orders ||--o{ order_proposals : "changes proposed in"
    orders ||--o| ai_conversations : "discussed in"
    ai_conversations ||--o{ ai_messages : "has"
    dishes ||--o{ order_items : "is ordered as"

    dish_categories {
        uuid id PK
        text name UK
        int sort_order
        bool is_active
    }
    dishes {
        uuid id PK
        uuid category_id FK
        text name
        text description "null"
        text image_path "null, Storage path"
        pricing_unit pricing_unit "per_guest|per_tray|per_weight|per_item"
        numeric unit_price ">= 0"
        text unit_label "null"
        char3 currency "ILS (OPEN 17)"
        numeric min_quantity "null, > 0"
        numeric serves_adults "null, > 0, adults one unit serves"
        bool is_available
        timestamptz created_at
        timestamptz updated_at
    }
    dish_dietary {
        uuid dish_id PK, FK "cascade"
        kashrut_class kashrut_class "null = unknown"
        bool is_vegetarian "null = unknown"
        bool is_vegan "null = unknown"
        timestamptz verified_at "null"
    }
    allergens {
        smallint id PK
        text name UK
    }
    dish_allergens {
        uuid dish_id PK, FK "cascade"
        smallint allergen_id PK, FK
        allergen_status status "contains|free; missing row = unknown"
    }
    time_slots {
        uuid id PK
        fulfillment_type fulfillment_type "pickup|delivery"
        smallint weekday "0=Sun..6=Sat, null = every day"
        time start_time
        time end_time "> start_time"
        int capacity "null, not enforced (OPEN 5)"
        bool is_active
    }
    blocked_dates {
        uuid id PK
        date date UK
        text reason "null, owner-only"
    }
    customers {
        uuid id PK
        uuid auth_user_id UK, FK "auth.users, null for non-account rows"
        text full_name
        text email "null, verified login email"
        text phone "null"
        timestamptz created_at
        timestamptz updated_at
    }
    events {
        uuid id PK
        uuid customer_id FK
        text event_type
        date event_date
        int adults ">= 0"
        int children ">= 0, adults + children > 0"
        int vegetarian_guests "subset; vegetarian + vegan <= total"
        int vegan_guests "subset, separate from vegetarian"
        int restricted_guests "subset: <= adults + children"
        text dietary_notes "null, free text, never parsed"
    }
    orders {
        uuid id PK
        uuid customer_id FK
        uuid event_id FK, UK
        order_status status "draft|pending_approval|approved|rejected"
        int version "optimistic lock, +1 per mutation"
        fulfillment_type fulfillment_type
        uuid slot_id FK "null, set null if the slot is deleted"
        timestamptz requested_at "event date at the slot start"
        text delivery_address "street, required when delivery"
        text delivery_city "null, a zone city when delivery"
        uuid delivery_zone_id FK "null, set at submission; set null on zone delete"
        numeric subtotal "null until submission"
        numeric delivery_fee "null; frozen from the zone at submission"
        numeric total "null until submission"
        timestamptz submitted_at "null"
        timestamptz decided_at "null"
        text decision_note "null, shown to customer"
        timestamptz created_at
        timestamptz updated_at
    }
    delivery_zones {
        uuid id PK
        text name UK
        numeric fee ">= 0"
        bool is_active
    }
    delivery_zone_cities {
        text city PK "normalized; one zone per city"
        uuid zone_id FK "cascade"
    }
    order_proposals {
        uuid id PK
        uuid order_id FK "cascade"
        text proposed_by "owner or assistant"
        int base_order_version "must match orders.version on accept"
        jsonb changes "add_item, set_quantity, remove_item"
        jsonb lines "proposed items with frozen prices"
        numeric price_before
        numeric price_after "incl. delivery fee"
        text note "null, shown to customer"
        text status "pending, accepted, declined, cancelled, expired"
        text customer_note "null, decline reason"
        timestamptz created_at
        timestamptz decided_at "null"
    }
    business_settings {
        smallint id PK "always 1"
        numeric child_portion "0 to 1, default 0.75"
        int lead_days "0 to 60, default 3"
        int assistant_daily_limit "0 to 1000, default 30, per 24h"
    }
    ai_conversations {
        uuid id PK
        uuid order_id FK,UK "cascade, one per order"
        timestamptz created_at
    }
    ai_messages {
        bigint id PK "identity, keeps the order"
        uuid conversation_id FK "cascade"
        text role "user, assistant"
        jsonb content "API content blocks, append-only"
        text customer_text "null, the customer's own words"
        timestamptz created_at
    }
    order_items {
        uuid id PK
        uuid order_id FK "cascade"
        uuid dish_id FK "dish delete blocked while referenced"
        numeric quantity "> 0, UK(order_id, dish_id)"
        text snapshot_name "frozen at submission"
        pricing_unit snapshot_pricing_unit
        numeric snapshot_unit_price
        numeric snapshot_line_total
    }
```

### Rules the diagram can't show
- **Unknown is not "no".** A `null` dietary field or a missing `dish_allergens` row means *unknown*. It is shown as unknown and never treated as safe.
- **Price snapshot.** While an order is `draft`, prices are read live from `dishes`. From `pending_approval` on, the `snapshot_*` columns are authoritative.
- **Status transitions** (enforced in services, with atomic conditional updates): `draft → pending_approval` (customer), then `pending_approval → approved | rejected` (owner). Anything else returns `409 invalid_transition`.
- **Ownership.** Customer access is always resolved from the verified token's `sub` → `customers.auth_user_id` (ADR 0005), never by email.
- **Guest groups are subsets** (OPEN_DECISIONS #4, decided 2026-11-02). Vegetarian, vegan and restricted guests are counted within adults + children. Vegetarian and vegan are **separate** groups, so vegetarian + vegan ≤ adults + children.
- **Pricing** (#14, #17, #18). Prices are in ILS, VAT included, and weight prices are per kg. Each line is rounded half-up to the agora, and the total is the sum of the lines.
- **Recommendations** (#3). A dish's quantity = eligible guests' portions ÷ `serves_adults`, rounded up (0.5 kg steps for weight, whole units otherwise) and never below `min_quantity`.
  - A child counts as `business_settings.child_portion` of an adult.
  - A vegan dish suits everyone. A vegetarian dish suits everyone except vegans. Any other dish, including one with unknown dietary data, excludes vegetarians and vegans.
- **`business_settings`** is a single, unrelated row of owner-editable settings.
- **Delivery fee** (#19). While draft, the fee is the current fee of the active zone containing `delivery_city`. At submission it is frozen into `orders.delivery_fee`, and `total` = sum of lines + fee.
- **Proposals** (#6). At most one `pending` per order (partial unique index). Accepting an owner proposal writes its frozen lines into `order_items`, recomputes the totals with the frozen delivery fee, and sets `orders.status = approved` and `decision_note = note`, all in one transaction guarded by `base_order_version`.
- **Assistant proposals** (Phase 4) use the same table with `proposed_by = assistant`, only on drafts, at live catalog prices. A new one cancels the open one; accepting one writes the items and bumps `version` but keeps the order `draft`. Submitting or withdrawing an order expires any open proposal.
- **Assistant messages** are stored exactly as exchanged with the model and never edited. The daily limit counts `ai_messages` with `customer_text` across the customer's orders in the last 24 hours.
- **Capacity** (#5). Orders that are `pending_approval` or `approved` hold their slot on their event date. Submitting checks `count < time_slots.capacity` while the slot row is locked (`SELECT … FOR UPDATE`).

## Planned (not migrated yet)

Nothing at the moment.
