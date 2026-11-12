# ERD: SQLite course database

Mirrors `schema.sql`. GitHub renders the diagram below.

```mermaid
erDiagram
    customers ||--o{ events : "plans"
    customers ||--o{ orders : "places"
    events ||--|| orders : "has one"
    dish_categories ||--o{ dishes : "groups"
    dishes ||--o| dish_dietary : "dietary info"
    dishes ||--o{ dish_allergens : "allergen status"
    allergens ||--o{ dish_allergens : "listed in"
    orders ||--o{ order_items : "contains"
    dishes ||--o{ order_items : "ordered as"
    delivery_zones |o--o{ orders : "delivers"
    orders ||--o{ ai_conversations : "chat about"
    ai_conversations ||--o{ ai_messages : "holds"
    orders ||--o{ ai_change_proposals : "proposed changes"
    ai_conversations |o--o{ ai_change_proposals : "suggested in"

    customers {
        TEXT id PK
        TEXT auth_user_id UK
        TEXT full_name
        TEXT email
        TEXT phone
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
    dish_categories {
        TEXT id PK
        TEXT name UK
        INTEGER sort_order
        INTEGER is_active
    }
    dishes {
        TEXT id PK
        TEXT category_id FK
        TEXT name
        TEXT description
        TEXT pricing_unit
        NUMERIC unit_price
        TEXT unit_label
        TEXT currency
        NUMERIC min_quantity
        INTEGER is_available
    }
    dish_dietary {
        TEXT dish_id PK,FK
        TEXT kashrut_class "null = unknown"
        INTEGER is_vegetarian "null = unknown"
        INTEGER is_vegan "null = unknown"
        TEXT verified_at
    }
    allergens {
        INTEGER id PK
        TEXT name UK
    }
    dish_allergens {
        TEXT dish_id PK,FK
        INTEGER allergen_id PK,FK
        TEXT status "contains | free | unknown"
    }
    delivery_zones {
        TEXT id PK
        TEXT name
        NUMERIC fee
        TEXT definition "JSON"
        INTEGER is_active
    }
    orders {
        TEXT id PK
        TEXT customer_id FK
        TEXT event_id FK,UK
        TEXT status "draft | pending_approval | approved | rejected"
        INTEGER version
        TEXT fulfillment_type "pickup | delivery"
        TEXT requested_at
        TEXT delivery_address
        TEXT delivery_zone_id FK
        NUMERIC subtotal
        NUMERIC delivery_fee
        NUMERIC total
        TEXT submitted_at
        TEXT decided_at
        TEXT decision_note
    }
    order_items {
        TEXT id PK
        TEXT order_id FK
        TEXT dish_id FK
        NUMERIC quantity
        TEXT snapshot_name
        TEXT snapshot_pricing_unit
        NUMERIC snapshot_unit_price
        NUMERIC snapshot_line_total
    }
    ai_conversations {
        TEXT id PK
        TEXT order_id FK
    }
    ai_messages {
        TEXT id PK
        TEXT conversation_id FK
        TEXT role "user | assistant | tool"
        TEXT content "JSON"
    }
    ai_change_proposals {
        TEXT id PK
        TEXT order_id FK
        TEXT conversation_id FK
        INTEGER base_order_version
        TEXT changes "JSON"
        NUMERIC price_before
        NUMERIC price_after
        TEXT status "pending | approved | rejected | expired | failed"
        TEXT executed_at
    }
```

`time_slots` and `blocked_dates` stand alone (no foreign keys), so they are not drawn.
A missing `dish_allergens` row means "unknown", never "free".
