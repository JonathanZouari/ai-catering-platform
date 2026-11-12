-- Availability: what the C1 event form asks for (date, time slot, delivery area).

CREATE TABLE delivery_zones (
  id         uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text          NOT NULL UNIQUE,
  fee        numeric(10,2) NOT NULL CHECK (fee >= 0),
  -- Shape depends on how zones are defined (OPEN #19); for now {"cities": [...]}.
  definition jsonb         NOT NULL,
  is_active  boolean       NOT NULL DEFAULT true
);

CREATE TABLE time_slots (
  id               uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
  fulfillment_type fulfillment_type NOT NULL,
  -- 0 = Sunday ... 6 = Saturday; NULL means every day.
  weekday          smallint         CHECK (weekday BETWEEN 0 AND 6),
  start_time       time             NOT NULL,
  end_time         time             NOT NULL,
  capacity         integer          CHECK (capacity > 0),  -- NULL = no limit (OPEN #5)
  is_active        boolean          NOT NULL DEFAULT true,
  CHECK (end_time > start_time)
);

CREATE TABLE blocked_dates (
  id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  date   date NOT NULL UNIQUE,
  reason text
);

-- Smallest quantity the business sells (OPEN #15); NULL = no minimum.
ALTER TABLE dishes ADD COLUMN min_quantity numeric(10,2) CHECK (min_quantity > 0);

ALTER TABLE orders ADD COLUMN delivery_zone_id uuid REFERENCES delivery_zones (id);
CREATE INDEX orders_delivery_zone_idx ON orders (delivery_zone_id);

-- Same reason as in 0001: no public Data API access.
ALTER TABLE delivery_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE blocked_dates ENABLE ROW LEVEL SECURITY;
