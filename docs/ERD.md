# Entity-relationship diagram

Diagrams for the planned schema in [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) (v0.2, not migrated yet). Column conventions:

- `*_agorot`: money in whole agorot, VAT-inclusive (₪85.50 = `8550`).
- `*_milli`: quantity in thousandths of the dish unit (3 trays = `3000`).
- Empty kashrut / vegetarian / vegan means **unknown**; a missing `dish_allergens` row means **unknown**, never allergen-free.
- `PK` primary key · `FK` foreign key · `UK` unique. `||--o{` = one required parent, zero or more children; `|o--o{` = optional parent.

## Overview (relationships only)

Every line is a foreign key. `orders` is the centre. `settings` and `calendar_overrides` have no foreign keys; the backend reads them for the daily guest limit.

```mermaid
erDiagram
  categories ||--o{ dishes : "contains"
  dishes ||--o{ dish_allergens : "has"
  allergens ||--o{ dish_allergens : "listed in"
  staff_users |o--o{ dishes : "verifies allergens"
  delivery_zones ||--o{ zone_cities : "covers"
  customers ||--o{ orders : "places"
  time_slots |o--o{ orders : "booked in"
  zone_cities |o--o{ orders : "delivers to city"
  delivery_zones |o--o{ orders : "priced by"
  orders ||--o{ order_items : "has lines"
  dishes ||--o{ order_items : "ordered as"
  orders ||--o{ order_events : "history"
  staff_users |o--o{ order_events : "acted"
  orders ||--o{ ai_conversations : "chat"
  ai_conversations ||--o{ ai_messages : "contains"
  orders ||--o{ ai_change_proposals : "suggestions"
  ai_conversations |o--o{ ai_change_proposals : "raised in"
  settings {
    int id PK "always 1"
  }
  calendar_overrides {
    date date PK
  }
```

## Menu

One unit and one price per dish; weight is priced per 100 g. Empty `qty_*` columns mean no recommended amount.

```mermaid
erDiagram
  categories ||--o{ dishes : "contains"
  dishes ||--o{ dish_allergens : "has"
  allergens ||--o{ dish_allergens : "listed in"
  categories {
    uuid id PK
    text name UK
    int sort_order
    bool is_active
  }
  dishes {
    uuid id PK
    uuid category_id FK
    text name
    text description
    text image_path
    text unit "tray, 100g, item, guest"
    text unit_label "e.g. tray for 10"
    int price_agorot "VAT-inclusive"
    int qty_per_adult_milli "recommendation"
    int qty_per_child_milli "recommendation"
    int qty_step_milli "stepper and rounding"
    int qty_min_milli
    text kashrut "meat, dairy, pareve, null = unknown"
    bool is_vegetarian "null = unknown"
    bool is_vegan "null = unknown"
    uuid allergens_verified_by FK "staff_users"
    timestamp allergens_verified_at
    bool is_available
    int sort_order
  }
  allergens {
    uuid id PK
    text name UK "Hebrew"
    int sort_order
  }
  dish_allergens {
    uuid dish_id PK, FK
    uuid allergen_id PK, FK
    text status "contains, may_contain, free"
  }
```

## Customers and orders

Statuses: `draft` → `pending_approval` → `approved` / `rejected`, plus `cancelled` and `completed`; every change writes an `order_events` row. `frozen` columns are filled at submission.

```mermaid
erDiagram
  customers ||--o{ orders : "places"
  orders ||--o{ order_items : "has lines"
  dishes ||--o{ order_items : "ordered as"
  orders ||--o{ order_events : "history"
  customers {
    uuid id PK
    text full_name
    text phone UK "digits only, one phone = one customer"
    text email
    text auth_user_id UK "reserved for login"
  }
  orders {
    uuid id PK
    uuid customer_id FK
    text access_token_hash UK "private order link"
    text status "draft to completed"
    int version "bumped on every change"
    text event_type
    date event_date
    uuid time_slot_id FK
    time slot_start "copied from slot"
    time slot_end "copied from slot"
    int adults "at least 1"
    int children
    int vegetarian "subset of guests"
    int vegan "subset of guests"
    int restricted "subset of guests"
    text dietary_notes
    text fulfillment "pickup, delivery"
    text city FK "zone_cities"
    text delivery_address
    uuid delivery_zone_id FK
    int delivery_fee_agorot "frozen"
    int subtotal_agorot "frozen"
    int total_agorot "frozen"
    int vat_rate_bp "frozen, 1800 = 18 percent"
    int vat_agorot "frozen"
    timestamp submitted_at
  }
  order_items {
    uuid id PK
    uuid order_id FK
    uuid dish_id FK
    int quantity_milli
    text snapshot_name "frozen"
    text snapshot_unit "frozen"
    text snapshot_kashrut "frozen"
    int snapshot_price_agorot "frozen"
    int line_total_agorot "frozen"
  }
  order_events {
    uuid id PK
    uuid order_id FK
    text from_status
    text to_status
    text actor_type "customer, staff, system"
    uuid staff_user_id FK
    text note
    timestamp created_at
  }
```

## AI assistant

A suggestion runs only if `base_order_version` still matches `orders.version`, and only once (`executed_at`). Chat messages are deleted 90 days after the event; suggestions stay.

```mermaid
erDiagram
  orders ||--o{ ai_conversations : "chat"
  ai_conversations ||--o{ ai_messages : "contains"
  orders ||--o{ ai_change_proposals : "suggestions"
  ai_conversations |o--o{ ai_change_proposals : "raised in"
  ai_conversations {
    uuid id PK
    uuid order_id FK
    timestamp created_at
  }
  ai_messages {
    uuid id PK
    uuid conversation_id FK
    text role "user, assistant, tool"
    json content
    timestamp created_at
  }
  ai_change_proposals {
    uuid id PK
    uuid order_id FK "one pending per order"
    uuid conversation_id FK
    int base_order_version "must match orders.version"
    json changes "typed operations"
    int price_before_agorot
    int price_after_agorot
    text status "pending, approved, rejected, expired, failed"
    timestamp decided_at
    timestamp executed_at "set once"
  }
```

## Delivery, availability and staff

Daily guest limit = `calendar_overrides.max_guests` if set, else `settings.default_max_guests_per_day`. A blocked date is an override with `is_blocked`. Time slots have no capacity.

```mermaid
erDiagram
  delivery_zones ||--o{ zone_cities : "covers"
  zone_cities |o--o{ orders : "delivers to"
  time_slots |o--o{ orders : "booked in"
  staff_users |o--o{ order_events : "acted"
  delivery_zones {
    uuid id PK
    text name UK
    int fee_agorot
    bool is_active
  }
  zone_cities {
    text city PK
    uuid zone_id FK
  }
  time_slots {
    uuid id PK
    text fulfillment "pickup, delivery"
    int weekday "0-6, null = every day"
    time start_time
    time end_time
    bool is_active
  }
  calendar_overrides {
    date date PK
    int max_guests "overrides default"
    bool is_blocked
    text reason
  }
  settings {
    int id PK "always 1"
    int default_max_guests_per_day
    int min_lead_days
    int vat_rate_bp
    text currency "ILS"
  }
  staff_users {
    uuid id PK
    text email UK
    text password_hash
    text full_name
    bool is_active
    timestamp last_login_at
  }
```
