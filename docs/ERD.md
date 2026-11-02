# Entity Relationship Diagram

Matches `database/migrations/20261102000000_initial_schema.sql`. Renders on GitHub (Mermaid).
`business_settings` is a single-row config table and has no relations, so it is omitted.

```mermaid
erDiagram
    customers ||--o{ events : plans
    customers ||--o{ orders : places
    events ||--|| orders : "has one"
    admin_users |o--o{ orders : decides
    delivery_zones |o--o{ orders : "delivered to"

    orders ||--o{ order_items : contains
    orders ||--o{ order_status_history : logs
    orders ||--o{ ai_conversations : has
    orders ||--o{ ai_change_proposals : receives

    dishes ||--o{ order_items : "ordered as"
    dish_categories ||--o{ dishes : groups
    dish_categories ||--o{ quantity_rules : "sized by"
    dishes ||--o| dish_dietary : has
    dishes ||--o{ dish_allergens : has
    allergens ||--o{ dish_allergens : flagged
    dishes ||--o{ dish_tag_links : tagged
    dish_tags ||--o{ dish_tag_links : applies

    ai_conversations ||--o{ ai_messages : contains
    ai_conversations |o--o{ ai_change_proposals : produces

    customers {
        uuid id PK
        uuid auth_user_id UK
        text full_name
        text email
        text phone
    }
    events {
        uuid id PK
        uuid customer_id FK
        text event_type
        date event_date
        int adults
        int children
        int vegetarian_guests
        int vegan_guests
        int restricted_guests
        text dietary_notes
    }
    orders {
        uuid id PK
        uuid customer_id FK
        uuid event_id FK
        order_status status
        int version
        fulfillment_type fulfillment_type
        timestamptz requested_at
        text delivery_address
        uuid delivery_zone_id FK
        numeric subtotal
        numeric delivery_fee
        numeric total
        uuid decided_by FK
        text decision_note
    }
    order_items {
        uuid id PK
        uuid order_id FK
        uuid dish_id FK
        numeric quantity
        text notes
        numeric snapshot_unit_price
        numeric snapshot_line_total
    }
    order_status_history {
        uuid id PK
        uuid order_id FK
        order_status from_status
        order_status to_status
        text actor_type
        uuid actor_id
    }
    admin_users {
        uuid id PK
        uuid auth_user_id UK
        text full_name
        text email UK
        bool is_active
    }
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
        pricing_unit pricing_unit
        numeric unit_price
        numeric min_quantity
        bool is_available
        timestamptz deleted_at
    }
    dish_dietary {
        uuid dish_id PK
        kashrut_class kashrut_class
        bool is_vegetarian
        bool is_vegan
    }
    allergens {
        smallint id PK
        text name UK
    }
    dish_allergens {
        uuid dish_id PK
        smallint allergen_id PK
        allergen_status status
    }
    dish_tags {
        uuid id PK
        text name UK
    }
    dish_tag_links {
        uuid dish_id PK
        uuid tag_id PK
    }
    quantity_rules {
        uuid id PK
        uuid category_id FK
        text guest_basis
        numeric amount_per_guest
        jsonb params
    }
    delivery_zones {
        uuid id PK
        text name
        numeric fee
        jsonb definition
    }
    time_slots {
        uuid id PK
        fulfillment_type fulfillment_type
        smallint weekday
        time start_time
        time end_time
        int capacity
    }
    blocked_dates {
        uuid id PK
        date date UK
        text reason
    }
    ai_conversations {
        uuid id PK
        uuid order_id FK
    }
    ai_messages {
        uuid id PK
        uuid conversation_id FK
        text role
        jsonb content
    }
    ai_change_proposals {
        uuid id PK
        uuid order_id FK
        uuid conversation_id FK
        int base_order_version
        jsonb changes
        numeric price_before
        numeric price_after
        proposal_status status
    }
```

`time_slots` and `blocked_dates` have no foreign keys. Orders are checked against them in backend logic.
