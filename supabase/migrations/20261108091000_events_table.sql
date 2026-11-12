-- Bring back a separate events table: one event can have several orders
-- (e.g. a quotation that is reworked into a new order after a rejection).
--
-- events = what the event is: who, what kind, when, how many guests, dietary needs.
-- orders = how one quotation for it is served and priced: slot, pickup/delivery,
--          address, items, totals, status.
--
-- orders keeps customer_id (every customer RLS policy filters on it), but a composite
-- FK (event_id, customer_id) -> events (id, customer_id) means an order can never
-- belong to a different customer than its event.

create table events (
  id             uuid primary key default gen_random_uuid(),
  customer_id    uuid not null references customers (id),
  event_type     text not null,
  event_date     date not null,
  adults         integer not null check (adults >= 1),
  children       integer not null default 0 check (children >= 0),
  vegetarian     integer not null default 0 check (vegetarian >= 0),
  vegan          integer not null default 0 check (vegan >= 0),
  restricted     integer not null default 0 check (restricted >= 0),
  dietary_notes  text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint ck_diet_within_guests check (vegetarian + vegan + restricted <= adults + children),
  constraint uq_events_id_customer unique (id, customer_id)
);
create index ix_events_customer on events (customer_id);
create index ix_events_date on events (event_date);

create trigger set_updated_at before update on public.events
  for each row execute function private.set_updated_at();

-- Move the existing event details out of orders: one event per order, reusing the
-- order's id so the link is trivial to set.
insert into events (id, customer_id, event_type, event_date, adults, children,
                    vegetarian, vegan, restricted, dietary_notes, created_at, updated_at)
select id, customer_id, event_type, event_date, adults, children,
       vegetarian, vegan, restricted, dietary_notes, created_at, updated_at
from orders;

alter table orders add column event_id uuid;
update orders set event_id = id;
alter table orders
  alter column event_id set not null,
  add constraint fk_orders_event foreign key (event_id, customer_id)
    references events (id, customer_id);
create index ix_orders_event on orders (event_id);

-- Dropping event_date also drops ix_orders_status_date; keep an index on status.
alter table orders
  drop constraint ck_diet_within_guests,
  drop column event_type,
  drop column event_date,
  drop column adults,
  drop column children,
  drop column vegetarian,
  drop column vegan,
  drop column restricted,
  drop column dietary_notes;
create index ix_orders_status on orders (status);

-- Access: same model as orders. Customers read their own events; writes go through
-- the backend (service_role). Staff manage everything.
revoke all on events from anon, authenticated;
grant select, insert, update, delete on events to authenticated;
alter table events enable row level security;

create policy "staff manage events" on events for all to authenticated
  using ((select private.is_staff())) with check ((select private.is_staff()));
create policy "customer reads own events" on events
  for select to authenticated using (customer_id = (select private.my_customer_id()));

alter publication supabase_realtime add table public.events;
