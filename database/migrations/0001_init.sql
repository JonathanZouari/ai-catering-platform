-- Postgres schema for Supabase, first cut of docs/DATABASE_SCHEMA.md.
-- dish_dietary is folded into dishes, since it is 1:1.
-- Not here yet: the AI tables and quantity_rules.

CREATE TYPE pricing_unit AS ENUM ('per_guest', 'per_tray', 'per_weight', 'per_item');
CREATE TYPE kashrut_class AS ENUM ('meat', 'dairy', 'pareve');
CREATE TYPE fulfillment_type AS ENUM ('pickup', 'delivery');
CREATE TYPE order_status AS ENUM ('draft', 'pending_approval', 'approved', 'rejected');
CREATE TYPE allergen_status AS ENUM ('contains', 'free', 'unknown');

CREATE TABLE dish_categories (
  id         uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text    NOT NULL UNIQUE,
  sort_order integer NOT NULL DEFAULT 0,
  is_active  boolean NOT NULL DEFAULT true
);

CREATE TABLE dishes (
  id            uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id   uuid          NOT NULL REFERENCES dish_categories (id),
  name          text          NOT NULL,
  description   text,
  image_path    text,
  pricing_unit  pricing_unit  NOT NULL,
  unit_price    numeric(10,2) NOT NULL CHECK (unit_price >= 0),
  unit_label    text,
  currency      char(3)       NOT NULL DEFAULT 'ILS',
  is_available  boolean       NOT NULL DEFAULT true,
  -- Dietary fields: NULL means unknown and must never be shown as "no" (decision 9).
  kashrut_class kashrut_class,
  is_vegetarian boolean,
  is_vegan      boolean,
  created_at    timestamptz   NOT NULL DEFAULT now(),
  updated_at    timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX dishes_category_idx ON dishes (category_id);

CREATE TABLE allergens (
  id   smallint PRIMARY KEY,
  name text     NOT NULL UNIQUE
);

-- A missing row means unknown.
CREATE TABLE dish_allergens (
  dish_id     uuid            NOT NULL REFERENCES dishes (id) ON DELETE CASCADE,
  allergen_id smallint        NOT NULL REFERENCES allergens (id),
  status      allergen_status NOT NULL,
  PRIMARY KEY (dish_id, allergen_id)
);
CREATE INDEX dish_allergens_allergen_idx ON dish_allergens (allergen_id);

CREATE TABLE customers (
  id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name  text        NOT NULL,
  email      text,
  phone      text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE events (
  id                uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id       uuid    NOT NULL REFERENCES customers (id),
  event_type        text    NOT NULL,
  event_date        date    NOT NULL,
  adults            integer NOT NULL CHECK (adults >= 0),
  children          integer NOT NULL CHECK (children >= 0),
  vegetarian_guests integer NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
  vegan_guests      integer NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
  restricted_guests integer NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
  dietary_notes     text,
  CHECK (adults + children > 0)
);
CREATE INDEX events_customer_idx ON events (customer_id);

CREATE TABLE orders (
  id               uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id      uuid             NOT NULL REFERENCES customers (id),
  event_id         uuid             NOT NULL UNIQUE REFERENCES events (id),
  status           order_status     NOT NULL DEFAULT 'draft',
  version          integer          NOT NULL DEFAULT 1,
  fulfillment_type fulfillment_type NOT NULL,
  requested_at     timestamptz      NOT NULL,
  delivery_address text,
  subtotal         numeric(10,2),
  delivery_fee     numeric(10,2),
  total            numeric(10,2),
  submitted_at     timestamptz,
  decided_at       timestamptz,
  decision_note    text,
  created_at       timestamptz      NOT NULL DEFAULT now(),
  updated_at       timestamptz      NOT NULL DEFAULT now(),
  CHECK (fulfillment_type = 'pickup' OR delivery_address IS NOT NULL)
);
CREATE INDEX orders_customer_idx ON orders (customer_id);
CREATE INDEX orders_status_idx ON orders (status);

CREATE TABLE order_items (
  id                    uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id              uuid          NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
  dish_id               uuid          NOT NULL REFERENCES dishes (id),
  quantity              numeric(10,2) NOT NULL CHECK (quantity > 0),
  -- Price snapshot, filled on submission; authoritative from pending_approval on.
  snapshot_name         text,
  snapshot_pricing_unit pricing_unit,
  snapshot_unit_price   numeric(10,2),
  snapshot_line_total   numeric(10,2),
  UNIQUE (order_id, dish_id)
);
CREATE INDEX order_items_dish_idx ON order_items (dish_id);

-- With no policies, Supabase's public Data API can read nothing here.
-- The backend connects as the table owner, which RLS does not restrict.
ALTER TABLE dish_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE dishes ENABLE ROW LEVEL SECURITY;
ALTER TABLE allergens ENABLE ROW LEVEL SECURITY;
ALTER TABLE dish_allergens ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
