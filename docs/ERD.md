# ERD: local SQLite schema (lesson 15 homework)

Source of truth: `database/schema.sql`. Rendered diagram: `docs/erd.svg` (also `docs/erd.png`). The mermaid block below renders on GitHub.
This is the SQLite subset of `DATABASE_SCHEMA.md` (the Supabase/Postgres draft):
the core an order needs, plus allergens. Delivery zones, time slots, blocked dates
and the AI conversation tables are left for the Supabase phase.

```mermaid
erDiagram
    customers ||--o{ events : "has"
    customers ||--o{ orders : "places"
    events ||--|| orders : "one event = one order"
    dish_categories ||--o{ dishes : "groups"
    orders ||--o{ order_items : "contains"
    dishes ||--o{ order_items : "appears in"
    dishes ||--o{ dish_allergens : ""
    allergens ||--o{ dish_allergens : ""

    customers {
        int id PK
        text full_name
        text phone
        text email
        text created_at
    }
    events {
        int id PK
        int customer_id FK
        text event_type
        text event_date
        int adults
        int children
        int vegetarian_guests
        int vegan_guests
        text dietary_notes
    }
    dish_categories {
        int id PK
        text name
        int sort_order
    }
    dishes {
        int id PK
        int category_id FK
        text name
        text description
        text pricing_unit
        real unit_price
        text kashrut
        int is_vegetarian
        int is_vegan
        int is_available
    }
    orders {
        int id PK
        int customer_id FK
        int event_id FK
        text status
        text fulfillment_type
        text delivery_address
        real subtotal
        real delivery_fee
        real total
        text decision_note
        text created_at
        text submitted_at
    }
    order_items {
        int id PK
        int order_id FK
        int dish_id FK
        real quantity
        text snapshot_name
        real snapshot_unit_price
        real snapshot_line_total
    }
    allergens {
        int id PK
        text name
    }
    dish_allergens {
        int dish_id PK_FK
        int allergen_id PK_FK
        text status
    }
```

## Relationship notes
- One customer, many events and many orders. The foreign key sits on the "many" side.
- One event has exactly one order (`orders.event_id` is a foreign key **and** unique).
- `order_items` resolves the many-to-many between orders and dishes. It also snapshots
  the dish name and unit price at submission, so later menu changes never rewrite
  an old order.
- `dish_allergens` resolves the many-to-many between dishes and allergens. Its primary
  key is the pair `(dish_id, allergen_id)`. A row says `contains` or `free`;
  a missing row means **unknown**, which the UI must never show as "free".
- Boolean columns use `1 / 0 / NULL`, and `NULL` means unknown, never "no".
