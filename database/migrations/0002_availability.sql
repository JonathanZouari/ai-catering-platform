-- Availability: what the C1 event form asks for (date, time slot, delivery area).

CREATE TABLE delivery_zones (
  id         INTEGER PRIMARY KEY,
  name       TEXT    NOT NULL UNIQUE,
  fee_minor  INTEGER NOT NULL CHECK (fee_minor >= 0),
  -- Shape depends on how zones are defined (OPEN #19); for now {"cities": [...]}.
  definition TEXT    NOT NULL CHECK (json_valid(definition)),
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE time_slots (
  id               INTEGER PRIMARY KEY,
  fulfillment_type TEXT    NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
  -- 0 = Sunday ... 6 = Saturday; NULL means every day.
  weekday          INTEGER CHECK (weekday BETWEEN 0 AND 6),
  start_time       TEXT    NOT NULL CHECK (start_time GLOB '[0-2][0-9]:[0-5][0-9]'),
  end_time         TEXT    NOT NULL CHECK (end_time GLOB '[0-2][0-9]:[0-5][0-9]'),
  capacity         INTEGER CHECK (capacity > 0),  -- NULL = no limit (OPEN #5)
  is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  -- Zero-padded HH:MM compares correctly as text.
  CHECK (end_time > start_time)
);

CREATE TABLE blocked_dates (
  id     INTEGER PRIMARY KEY,
  date   TEXT NOT NULL UNIQUE CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'),
  reason TEXT
);

-- Smallest quantity the business sells (OPEN #15); NULL = no minimum.
ALTER TABLE dishes ADD COLUMN min_quantity REAL CHECK (min_quantity > 0);

ALTER TABLE orders ADD COLUMN delivery_zone_id INTEGER REFERENCES delivery_zones (id);
