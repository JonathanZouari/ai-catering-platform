# Entity relationship diagram

The Postgres schema from `supabase/migrations/20261105000000_schema.sql`.
Column details and rules are in `DATABASE_SCHEMA.md`.

Notes:

- Every table except `allergens` and `dish_dietary`/`dish_allergens` (which hang off
  `dishes`) has a `caterer_id`. To keep the diagram readable, only the top-level
  tables draw a line to `caterers`; the rest reach it through their parent, and
  composite foreign keys on `(caterer_id, ...)` keep the whole chain in one caterer.
- Money columns are integer hundredths (12.50 is 1250). Ids are 32 hex characters.
- `quantity_rules.caterer_id` is nullable: null is the platform default.

```mermaid
erDiagram
    caterers {
        text id PK
        text slug UK
        text name
        text logo_path
        text brand_color
        text contact_phone
        text notification_email
        text kashrut_status
        text kashrut_certificate_path
        text kashrut_mixing_rule "block | warn"
        text currency
        integer ai_monthly_message_limit
        integer is_active
        text created_at
        text updated_at
    }

    caterer_users {
        text id PK
        text caterer_id FK
        text auth_user_id UK "Supabase Auth user"
        text created_at
    }

    customers {
        text id PK
        text caterer_id FK
        text full_name
        text phone
        text email
        text created_at
        text updated_at
    }

    events {
        text id PK
        text caterer_id FK
        text customer_id FK
        text event_type
        text event_date
        integer adults
        integer children
        integer vegetarian_guests
        integer vegan_guests
        integer restricted_guests
        text dietary_notes
        text created_at
        text updated_at
    }

    dish_categories {
        text id PK
        text caterer_id FK
        text name
        text category_type "salad | main | side | dessert | drink | other"
        integer sort_order
        integer is_active
        text created_at
        text updated_at
    }

    dishes {
        text id PK
        text caterer_id FK
        text category_id FK
        text name
        text description
        text image_path
        text pricing_unit "per_guest | per_tray | per_weight | per_item"
        integer unit_price
        text unit_label
        integer servings_per_unit
        integer calories_per_portion
        text portion_description
        integer min_quantity
        integer is_available
        text created_at
        text updated_at
    }

    dish_dietary {
        text dish_id PK, FK
        text kashrut_class "meat | dairy | pareve, null = unknown"
        integer is_vegetarian "null = unknown"
        integer is_vegan "null = unknown"
        text verified_at
    }

    allergens {
        integer id PK
        text name UK
    }

    dish_allergens {
        text dish_id PK, FK
        integer allergen_id PK, FK
        text status "contains | free | unknown"
    }

    delivery_zones {
        text id PK
        text caterer_id FK
        text name
        integer fee
        text definition "JSON"
        integer is_active
    }

    time_slots {
        text id PK
        text caterer_id FK
        text fulfillment_type "pickup | delivery"
        integer weekday "0-6"
        text start_time
        text end_time
        integer capacity
        integer is_active
    }

    blocked_dates {
        text id PK
        text caterer_id FK
        text date
        text reason
    }

    quantity_rules {
        text id PK
        text caterer_id FK "null = platform default"
        text category_type
        integer portions_per_adult
        integer portions_per_child
    }

    orders {
        text id PK
        text caterer_id FK
        text access_token_hash UK
        text customer_id FK
        text event_id FK, UK
        text status "draft | pending_approval | approved | rejected"
        integer version
        text fulfillment_type "pickup | delivery"
        text requested_at
        text time_slot_id FK
        text delivery_city
        text delivery_address
        text delivery_zone_id FK
        integer subtotal
        integer delivery_fee
        integer total
        integer kashrut_warning_acknowledged
        text submitted_at
        text decided_at
        text decision_note
        text created_at
        text updated_at
    }

    order_items {
        text id PK
        text caterer_id FK
        text order_id FK
        text dish_id FK
        integer quantity
        text snapshot_name
        text snapshot_pricing_unit
        integer snapshot_unit_price
        integer snapshot_line_total
    }

    ai_conversations {
        text id PK
        text caterer_id FK
        text order_id FK, UK
        text created_at
    }

    ai_messages {
        text id PK
        text caterer_id FK
        text conversation_id FK
        text role "user | assistant | tool"
        text content "JSON"
        text created_at
    }

    ai_change_proposals {
        text id PK
        text caterer_id FK
        text order_id FK
        text conversation_id FK
        integer base_order_version
        text changes "JSON"
        text rationale
        integer price_before
        integer price_after
        text status "pending | approved | rejected | expired | failed"
        text created_at
        text decided_at
        text executed_at
    }

    ai_usage {
        text caterer_id PK, FK
        text month PK
        integer message_count
    }

    caterers ||--o{ caterer_users : "has logins"
    caterers ||--o{ customers : "has"
    caterers ||--o{ dish_categories : "has menu"
    caterers ||--o{ delivery_zones : "delivers to"
    caterers ||--o{ time_slots : "offers"
    caterers ||--o{ blocked_dates : "closes on"
    caterers |o--o{ quantity_rules : "overrides"
    caterers ||--o{ ai_usage : "uses AI"

    customers ||--o{ events : "plans"
    customers ||--o{ orders : "places"
    events ||--o| orders : "ordered as"

    dish_categories ||--o{ dishes : "contains"
    dishes ||--o| dish_dietary : "dietary info"
    dishes ||--o{ dish_allergens : "allergen status"
    allergens ||--o{ dish_allergens : "listed in"

    orders ||--o{ order_items : "contains"
    dishes ||--o{ order_items : "ordered as"
    delivery_zones |o--o{ orders : "delivery zone"
    time_slots |o--o{ orders : "time slot"

    orders ||--o| ai_conversations : "chat"
    ai_conversations ||--o{ ai_messages : "messages"
    orders ||--o{ ai_change_proposals : "proposals"
    ai_conversations |o--o{ ai_change_proposals : "proposed in"
```
