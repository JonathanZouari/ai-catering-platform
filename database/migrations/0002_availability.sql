-- Availability: pickup/delivery time slots and blocked dates.
-- Mirrors backend/app/models/availability.py and docs/DATABASE_SCHEMA.md.
-- RLS is on with no policies: only the backend's privileged connection reads/writes (ADR 0002).

create type fulfillment_type as enum ('pickup', 'delivery');

create table time_slots (
  id uuid primary key default gen_random_uuid(),
  fulfillment_type fulfillment_type not null,
  weekday smallint, -- 0 = Sunday ... 6 = Saturday; null = every day
  start_time time not null,
  end_time time not null,
  capacity int check (capacity > 0), -- not enforced yet, OPEN_DECISIONS #5
  is_active boolean not null default true,
  constraint time_slots_order check (end_time > start_time),
  constraint time_slots_weekday check (weekday between 0 and 6)
);

create table blocked_dates (
  id uuid primary key default gen_random_uuid(),
  date date not null unique,
  reason text
);

alter table time_slots enable row level security;
alter table blocked_dates enable row level security;
