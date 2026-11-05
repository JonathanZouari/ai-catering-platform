# ERD — Supabase (project `ai-catering-platform`, schema `public`)

Source of truth: `supabase/migrations/20261105000000_init.sql`. Money = integer agorot. NULL in dietary/allergen columns = unknown, never "no".

```mermaid
erDiagram
  customers ||--o{ events : "has"
  customers ||--o{ orders : "places"
  events ||--o| orders : "one order per event"
  delivery_zones |o--o{ orders : "delivered to"
  orders ||--o{ order_items : "contains"
  dishes ||--o{ order_items : "ordered as"
  dish_categories ||--o{ dishes : "groups"
  dishes ||--o| dish_dietary : "has"
  dishes ||--o{ dish_allergens : "has"
  allergens ||--o{ dish_allergens : "classifies"
  orders ||--o{ ai_conversations : "has"
  ai_conversations ||--o{ ai_messages : "has"
  orders ||--o{ ai_change_proposals : "has"
  ai_conversations |o--o{ ai_change_proposals : "produced"

  customers {
    uuid id PK
    text full_name
    text email
    text phone
    timestamptz created_at
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
    text description
    text image_path "dish-images bucket"
    text pricing_unit "per_guest|per_tray|per_weight|per_item"
    int unit_price
    text unit_label
    numeric min_quantity
    bool is_available
    timestamptz created_at
  }
  dish_dietary {
    uuid dish_id PK, FK
    text kashrut_class "meat|dairy|pareve"
    bool is_vegetarian
    bool is_vegan
    timestamptz verified_at
  }
  allergens {
    smallint id PK
    text name UK
  }
  dish_allergens {
    uuid dish_id PK, FK
    smallint allergen_id PK, FK
    text status "contains|free"
  }
  delivery_zones {
    uuid id PK
    text name
    int fee
    jsonb definition
    bool is_active
  }
  time_slots {
    uuid id PK
    text fulfillment_type "pickup|delivery"
    smallint weekday
    time start_time
    time end_time
    int capacity
    bool is_active
  }
  blocked_dates {
    date date PK
    text reason
  }
  orders {
    uuid id PK
    uuid customer_id FK
    uuid event_id FK, UK
    text status "draft|pending_approval|approved|rejected"
    int version
    text fulfillment_type
    timestamptz requested_at
    text delivery_address
    uuid delivery_zone_id FK
    int subtotal
    int delivery_fee
    int total
    timestamptz submitted_at
    timestamptz decided_at
    text decision_note
    timestamptz created_at
  }
  order_items {
    uuid id PK
    uuid order_id FK
    uuid dish_id FK
    numeric quantity
    text snapshot_name
    text snapshot_pricing_unit
    int snapshot_unit_price
    int snapshot_line_total
  }
  ai_conversations {
    uuid id PK
    uuid order_id FK
    timestamptz created_at
  }
  ai_messages {
    uuid id PK
    uuid conversation_id FK
    text role "user|assistant|tool"
    jsonb content
    timestamptz created_at
  }
  ai_change_proposals {
    uuid id PK
    uuid order_id FK
    uuid conversation_id FK
    int base_order_version
    jsonb changes
    int price_before
    int price_after
    text status "pending|approved|rejected|expired|failed"
    timestamptz created_at
    timestamptz decided_at
    timestamptz executed_at
  }
```

`time_slots` and `blocked_dates` have no foreign keys: they are availability rules the backend checks against `orders.requested_at`.
Unique `(order_id, dish_id)` on `order_items`; at most one `pending` proposal per order (partial unique index).

## Cloud setup (Supabase project `ai-catering-platform`, ref `bbefeovnviriretrdlxl`, eu-central-1)

- **Schema:** 15 tables, migrations in `supabase/migrations/` (copies in `database/migrations/`).
- **Seed:** `supabase/seed.sql` (catalog + 3 demo customers), `supabase/seed_demo_more.sql` + `fix_totals.sql` (5 more customers, orders, one AI proposal). 8 fictitious customers in total.
- **Storage:** public-read bucket `dish-images` (JPEG/PNG/WebP, max 5MB); writes only for admin.
- **Auth + RLS:** email/password login. RLS on every table. Catalog is public-read; customers see only their own events/orders (editable while `draft`); admin = `app_metadata.role = 'admin'` (full access). `customers.auth_user_id` links a customer to `auth.users`.
- **Realtime:** `orders`, `order_items`, `ai_change_proposals`, `ai_messages`, `dishes` are in the `supabase_realtime` publication.
- **Demo users** (password shared privately, not in the repo): `admin.demo@example.com` (admin), `dana.demo@example.com` (customer, owns a draft order).
