-- Columns the basic order flow needs (PR #48 review), per docs/DATABASE_SCHEMA.md:
--   events:      vegetarian_guests, vegan_guests, restricted_guests
--   orders:      fulfillment_type, requested_at, delivery_address
--   order_items: price snapshot, frozen when the order is submitted
--
-- The linked project already holds rows (the demo order), so NOT NULL columns without a lasting
-- default are added nullable, backfilled, then set NOT NULL.

-- ---------------------------------------------------------------------------------------------
-- events: dietary guest counts
-- ---------------------------------------------------------------------------------------------
-- Whether these are subsets of adults + children, and whether vegan is a subset of vegetarian,
-- is still OPEN #4, so only the non-negative checks are enforced here.
alter table public.events
  add column vegetarian_guests int not null default 0 check (vegetarian_guests >= 0),
  add column vegan_guests int not null default 0 check (vegan_guests >= 0),
  add column restricted_guests int not null default 0 check (restricted_guests >= 0);

-- ---------------------------------------------------------------------------------------------
-- orders: fulfillment
-- ---------------------------------------------------------------------------------------------
create type public.fulfillment_type as enum ('pickup', 'delivery');

alter table public.orders
  add column fulfillment_type public.fulfillment_type,
  add column requested_at timestamptz,  -- requested pickup/delivery time
  add column delivery_address text;

-- Backfill existing rows: pickup at noon (Israel time) on the event date.
update public.orders o
set fulfillment_type = 'pickup',
    requested_at = (e.event_date + time '12:00') at time zone 'Asia/Jerusalem'
from public.events e
where e.id = o.event_id
  and (o.fulfillment_type is null or o.requested_at is null);

alter table public.orders
  alter column fulfillment_type set not null,
  alter column requested_at set not null,
  add constraint orders_delivery_address_required check (
    fulfillment_type <> 'delivery' or nullif(btrim(delivery_address), '') is not null
  );

-- ---------------------------------------------------------------------------------------------
-- order_items: price snapshot
-- ---------------------------------------------------------------------------------------------
-- While an order is a draft, prices are read live from dishes. On submission the backend fills
-- these columns and they become authoritative, so later menu price changes don't alter a quote.
alter table public.order_items
  add column snapshot_name text,
  add column snapshot_pricing_unit public.pricing_unit,
  add column snapshot_unit_price numeric(10, 2) check (snapshot_unit_price >= 0),
  add column snapshot_line_total numeric(10, 2) check (snapshot_line_total >= 0),
  add constraint order_items_snapshot_complete check (
    num_nulls(snapshot_name, snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total)
      in (0, 4)
  );

-- Backfill: freeze items of orders that were already submitted. quantity x unit_price matches
-- the demo data only; the real line-total formula is the backend's job (OPEN #3).
update public.order_items i
set snapshot_name = d.name,
    snapshot_pricing_unit = d.pricing_unit,
    snapshot_unit_price = d.unit_price,
    snapshot_line_total = round(i.quantity * d.unit_price, 2)
from public.dishes d, public.orders o
where d.id = i.dish_id
  and o.id = i.order_id
  and o.status <> 'draft'
  and i.snapshot_name is null;
