# CaterKing database: ERD

18 tables in four groups. The diagram is generated from the SQLAlchemy models by `scripts/erd.py`, so it always matches the code. It shows keys plus a few columns per table; full columns are in [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md).

| Group | Tables |
|---|---|
| Menu | `dish_categories` → `dishes` → `dish_dietary` (1:1), `dish_allergens` (many-to-many with `allergens`), `quantity_rules` (1 per category) |
| Ordering | `customers` → `events` → `orders` → `order_items` → `dishes` |
| Logistics | `time_slots`, `delivery_zones` (both optional on an order), `blocked_dates`, `geocode_cache` |
| AI assistant | `orders` → `ai_conversations` (1:1) → `ai_messages`; `ai_change_proposals` (per order, optional conversation) |
| Settings | `business_settings` (one row) |

`||` = exactly one, `|o` = zero or one, `o{` = zero or more.

```mermaid
erDiagram
  allergens {
    int id PK
    str name
  }
  blocked_dates {
    uuid id PK
    date date
    str reason
  }
  business_settings {
    bool id PK
    int lead_time_days
    int edit_cutoff_hours
    numeric min_food_total
  }
  customers {
    uuid id PK
    str full_name
    str email
    str phone
  }
  delivery_zones {
    uuid id PK
    str name
    numeric fee
    object definition
  }
  dish_categories {
    uuid id PK
    str name_he
    str name_ar
    str name_en
  }
  geocode_cache {
    str address_norm PK
    float lat
    float lon
    bool found
  }
  time_slots {
    uuid id PK
    FulfillmentType fulfillment_type
    int weekday
    time start_time
  }
  dishes {
    uuid id PK
    uuid category_id FK
    str name_he
    str name_ar
    str name_en
  }
  events {
    uuid id PK
    uuid customer_id FK
    str event_type
    date event_date
    int adults
  }
  quantity_rules {
    uuid id PK
    uuid category_id FK
    numeric per_adult
    numeric per_child
    numeric round_step
  }
  dish_allergens {
    uuid dish_id PK,FK
    int allergen_id PK,FK
    AllergenStatus status
  }
  dish_dietary {
    uuid dish_id PK,FK
    KashrutClass kashrut_class
    bool is_vegetarian
    bool is_vegan
  }
  orders {
    uuid id PK
    uuid customer_id FK
    uuid event_id FK
    uuid time_slot_id FK
    uuid delivery_zone_id FK
    OrderStatus status
    int version
    str access_token_hash
  }
  ai_conversations {
    uuid id PK
    uuid order_id FK
    object created_at
  }
  order_items {
    uuid id PK
    uuid order_id FK
    uuid dish_id FK
    numeric quantity
    str snapshot_name
    PricingUnit snapshot_pricing_unit
  }
  ai_change_proposals {
    uuid id PK
    uuid order_id FK
    uuid conversation_id FK
    int base_order_version
    object changes
    object diff
  }
  ai_messages {
    uuid id PK
    uuid conversation_id FK
    int seq
    str role
    object content
  }
  dish_categories ||--o{ dishes : category_id
  customers ||--o{ events : customer_id
  dish_categories ||--|o quantity_rules : category_id
  dishes ||--o{ dish_allergens : dish_id
  allergens ||--o{ dish_allergens : allergen_id
  dishes ||--|o dish_dietary : dish_id
  time_slots |o--o{ orders : time_slot_id
  customers ||--o{ orders : customer_id
  delivery_zones |o--o{ orders : delivery_zone_id
  events ||--o{ orders : event_id
  orders ||--|o ai_conversations : order_id
  dishes ||--o{ order_items : dish_id
  orders ||--o{ order_items : order_id
  orders ||--o{ ai_change_proposals : order_id
  ai_conversations |o--o{ ai_change_proposals : conversation_id
  ai_conversations ||--o{ ai_messages : conversation_id
```

## Try it in SQLite

```bash
cd backend
DATABASE_URL=sqlite:///./caterking_dev.db uv run python -m app.migrate     # tables + allergens + settings
sqlite3 caterking_dev.db < ../database/sqlite/demo_seed.sql                # demo menu and one order
sqlite3 -header -column caterking_dev.db                                   # explore
```

The demo seed adds 3 categories, 7 dishes (he/ar/en), dietary rows, allergens, 2 time slots, a delivery zone, a blocked date, and one customer with an event and an order waiting for approval.

One order across five tables (`orders` → `customers`, `events`, `order_items` → `dishes` → `dish_categories`):

```sql
SELECT c.full_name AS customer, e.event_type AS event, e.event_date AS date, o.status,
       d.name_en AS dish, cat.name_en AS category, i.quantity AS qty, i.snapshot_line_total AS line_total
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN events e ON e.id = o.event_id
JOIN order_items i ON i.order_id = o.id
JOIN dishes d ON d.id = i.dish_id
JOIN dish_categories cat ON cat.id = d.category_id;
```
```
customer       event     date        status            dish            category  qty  line_total
-------------  --------  ----------  ----------------  --------------  --------  ---  ----------
דנה כהן (דמו)  birthday  2026-11-16  pending_approval  Schnitzel       Mains     3    360       
דנה כהן (דמו)  birthday  2026-11-16  pending_approval  Garden salad    Salads    2    180       
דנה כהן (דמו)  birthday  2026-11-16  pending_approval  Chocolate cake  Desserts  1    85
```

The many-to-many link between dishes and allergens (a missing row means *unknown*, never "free"):

```sql
SELECT d.name_en AS dish, a.name AS allergen, da.status
FROM dish_allergens da
JOIN dishes d ON d.id = da.dish_id
JOIN allergens a ON a.id = da.allergen_id
ORDER BY d.name_en;
```
```
dish            allergen  status  
--------------  --------  --------
Chocolate cake  milk      contains
Chocolate cake  eggs      contains
Chocolate cake  gluten    contains
Garden salad    peanuts   free    
Hummus          sesame    contains
Schnitzel       gluten    contains
Schnitzel       eggs      contains
```

Regenerate the diagram after changing a model: `cd backend && PYTHONPATH=. uv run python ../scripts/erd.py`.
