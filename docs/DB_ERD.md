# SQLite ERD

Entity-relationship diagram of `backend/app/db/schema.sql`, generated from the real database (`PRAGMA table_info` / `foreign_key_list`). GitHub renders the diagram below.

Notation: `PK` primary key, `FK` foreign key, `UK` unique. Line ends: `||` exactly one, `|o` zero or one, `o{` zero or many.

```mermaid
erDiagram
    ai_change_proposals {
        TEXT id PK
        TEXT order_id FK
        TEXT conversation_id FK
        INTEGER base_order_version
        TEXT changes
        INTEGER price_before
        INTEGER price_after
        TEXT status
        TEXT created_at
        TEXT decided_at
        TEXT executed_at
    }
    ai_conversations {
        TEXT id PK
        TEXT order_id FK
        TEXT created_at
    }
    ai_messages {
        TEXT id PK
        TEXT conversation_id FK
        TEXT role
        TEXT content
        TEXT created_at
    }
    allergens {
        INTEGER id PK
        TEXT name UK
    }
    blocked_dates {
        TEXT date PK
        TEXT reason
    }
    customers {
        TEXT id PK
        TEXT full_name
        TEXT email
        TEXT phone
        TEXT created_at
    }
    delivery_zones {
        TEXT id PK
        TEXT name
        INTEGER fee
        TEXT definition
        INTEGER is_active
    }
    dish_allergens {
        TEXT dish_id PK,FK
        INTEGER allergen_id PK,FK
        TEXT status
    }
    dish_categories {
        TEXT id PK
        TEXT name UK
        INTEGER sort_order
        INTEGER is_active
    }
    dish_dietary {
        TEXT dish_id PK,FK
        TEXT kashrut_class
        INTEGER is_vegetarian
        INTEGER is_vegan
        TEXT verified_at
    }
    dishes {
        TEXT id PK
        TEXT category_id FK
        TEXT name
        TEXT description
        TEXT image_path
        TEXT pricing_unit
        INTEGER unit_price
        TEXT unit_label
        REAL min_quantity
        INTEGER is_available
        TEXT created_at
    }
    events {
        TEXT id PK
        TEXT customer_id FK
        TEXT event_type
        TEXT event_date
        INTEGER adults
        INTEGER children
        INTEGER vegetarian_guests
        INTEGER vegan_guests
        INTEGER restricted_guests
        TEXT dietary_notes
    }
    order_items {
        TEXT id PK
        TEXT order_id FK
        TEXT dish_id FK
        REAL quantity
        TEXT snapshot_name
        TEXT snapshot_pricing_unit
        INTEGER snapshot_unit_price
        INTEGER snapshot_line_total
    }
    orders {
        TEXT id PK
        TEXT customer_id FK
        TEXT event_id FK,UK
        TEXT status
        INTEGER version
        TEXT fulfillment_type
        TEXT requested_at
        TEXT delivery_address
        TEXT delivery_zone_id FK
        INTEGER subtotal
        INTEGER delivery_fee
        INTEGER total
        TEXT submitted_at
        TEXT decided_at
        TEXT decision_note
        TEXT created_at
    }
    time_slots {
        TEXT id PK
        TEXT fulfillment_type
        INTEGER weekday
        TEXT start_time
        TEXT end_time
        INTEGER capacity
        INTEGER is_active
    }
    ai_conversations |o--o{ ai_change_proposals : "conversation_id"
    orders ||--o{ ai_change_proposals : "order_id"
    orders ||--o{ ai_conversations : "order_id"
    ai_conversations ||--o{ ai_messages : "conversation_id"
    allergens ||--o{ dish_allergens : "allergen_id"
    dishes ||--o{ dish_allergens : "dish_id"
    dishes ||--o| dish_dietary : "dish_id"
    dish_categories ||--o{ dishes : "category_id"
    customers ||--o{ events : "customer_id"
    dishes ||--o{ order_items : "dish_id"
    orders ||--o{ order_items : "order_id"
    delivery_zones |o--o{ orders : "delivery_zone_id"
    events ||--o| orders : "event_id"
    customers ||--o{ orders : "customer_id"
```

## Notes
- One order per event (`orders.event_id` is unique); an order belongs to one customer.
- `order_items` is unique on (`order_id`, `dish_id`). Its `snapshot_*` columns freeze name and price on submission.
- `dish_dietary` is 1:1 with `dishes`; `dish_allergens` is the many-to-many link to `allergens`. A missing row means unknown.
- At most one `pending` row per order in `ai_change_proposals` (partial unique index, not shown as a relationship).
- Money is stored as integer agorot; dates are ISO-8601 text.
- `delivery_zones` is optional on an order; `time_slots` and `blocked_dates` stand alone (availability rules, no foreign keys).
