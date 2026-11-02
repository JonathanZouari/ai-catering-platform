-- Delivery zones as lists of cities, one fee per zone (OPEN_DECISIONS #19, decided 2026-11-02).
-- Replaces the draft's `definition jsonb`: a city table makes "one zone per city" a key.

create table delivery_zones (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  fee numeric(10, 2) not null check (fee >= 0), -- ILS, VAT included (#14)
  is_active boolean not null default true
);

create table delivery_zone_cities (
  city text primary key, -- normalized: trimmed, single spaces; a city is in at most one zone
  zone_id uuid not null references delivery_zones(id) on delete cascade
);
create index delivery_zone_cities_zone_id_idx on delivery_zone_cities (zone_id);

alter table orders
  add column delivery_city text,
  -- the zone whose fee was frozen at submission; deleting the zone keeps the frozen fee
  add column delivery_zone_id uuid references delivery_zones(id) on delete set null;

alter table delivery_zones enable row level security;
alter table delivery_zone_cities enable row level security;
