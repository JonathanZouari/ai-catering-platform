# Database ERD (SQLite prototype)

Entity-relationship diagram of `database/migrations/0001_initial.sql`. Only keys and the columns that carry
business meaning are shown; the migration file is the full definition. Design notes are in
[DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) and [ADR 0005](ADR/0005-sqlite-prototype-database.md).

```mermaid
erDiagram
    customers ||--o{ events : "plans"
    customers ||--o{ orders : "places"
    events ||--o| orders : "is ordered in"
    orders ||--o{ order_items : "contains"
    dishes ||--o{ order_items : "is ordered as"
    delivery_zones |o--o{ orders : "delivers to"
    dish_categories ||--o{ dishes : "groups"
    dishes ||--o| dish_dietary : "has"
    dishes ||--o{ dish_allergens : "is rated for"
    allergens ||--o{ dish_allergens : "is rated in"
    orders ||--o{ ai_conversations : "has"
    ai_conversations ||--o{ ai_messages : "holds"
    orders ||--o{ ai_change_proposals : "receives"
    ai_conversations |o--o{ ai_change_proposals : "produces"

    customers {
        text id PK
        text full_name
        text email
        text phone
    }
    events {
        text id PK
        text customer_id FK
        text event_type
        text event_date
        int adults
        int children
        int vegetarian_guests
        int vegan_guests
        int restricted_guests
    }
    orders {
        text id PK
        text customer_id FK
        text event_id FK "unique"
        text status "draft, pending_approval, approved, rejected"
        int version "optimistic lock"
        text fulfillment_type "pickup or delivery"
        text delivery_zone_id FK
        int subtotal "agorot, frozen at submission"
        int delivery_fee "agorot"
        int total "agorot"
    }
    order_items {
        text id PK
        text order_id FK
        text dish_id FK
        real quantity
        int snapshot_unit_price "agorot, set on submission"
        int snapshot_line_total "agorot, set on submission"
    }
    dish_categories {
        text id PK
        text name "unique"
        int sort_order
        int is_active
    }
    dishes {
        text id PK
        text category_id FK
        text name
        text pricing_unit "per_guest, per_tray, per_weight, per_item"
        int unit_price "agorot"
        text currency
        int is_available
    }
    dish_dietary {
        text dish_id PK, FK
        text kashrut_class "meat, dairy, pareve, or NULL"
        int is_vegetarian "NULL means unknown"
        int is_vegan "NULL means unknown"
    }
    allergens {
        int id PK
        text name "unique"
    }
    dish_allergens {
        text dish_id PK, FK
        int allergen_id PK, FK
        text status "contains, free, unknown"
    }
    delivery_zones {
        text id PK
        text name
        int fee "agorot"
        text definition "JSON, shape is OPEN decision 19"
    }
    time_slots {
        text id PK
        text fulfillment_type
        int weekday "NULL means every day"
        text start_time
        text end_time
        int capacity
    }
    blocked_dates {
        text id PK
        text date "unique"
        text reason
    }
    ai_conversations {
        text id PK
        text order_id FK
    }
    ai_messages {
        text id PK
        text conversation_id FK
        text role "user, assistant, tool"
        text content "JSON"
    }
    ai_change_proposals {
        text id PK
        text order_id FK
        text conversation_id FK
        int base_order_version "must equal orders.version"
        text changes "JSON"
        int price_before "agorot"
        int price_after "agorot"
        text status "pending, approved, rejected, expired, failed"
    }
```

## Reading the diagram

- `time_slots` and `blocked_dates` have no foreign keys. They are availability rules that the
  backend checks against an order's requested date and time.
- **No row means unknown.** A dish with no `dish_allergens` row for an allergen has unknown status for it,
  and `NULL` in `dish_dietary` means not provided. Neither is ever treated as "free" or "no".
- **Price snapshot.** While an order is a `draft`, prices are read live from `dishes`. On submission
  the `snapshot_*` columns on `order_items` and the totals on `orders` become authoritative.
- **One pending proposal per order** is enforced by a partial unique index on `ai_change_proposals`.
- Deleting an order cascades to its items, conversations, messages and proposals. Deleting a dish
  cascades to its dietary and allergen rows.
