-- Replace text + CHECK with real Postgres enum types.
-- The schema no longer has to run on SQLite, so the portable workaround is not needed.
-- This also closes four columns that had no check at all:
--   order_events.from_status / to_status, order_items.snapshot_kashrut / snapshot_unit.
--
-- Adding a value later:   alter type order_status add value 'x';  (cannot be used in the same transaction)
-- Removing or renaming a value is harder (rename works, removal needs a new type), so think before adding.

create type dish_unit       as enum ('tray', '100g', 'item', 'guest');
create type kashrut         as enum ('meat', 'dairy', 'pareve');
create type allergen_status as enum ('contains', 'may_contain', 'free');
create type fulfillment     as enum ('pickup', 'delivery');
create type order_status    as enum ('draft', 'pending_approval', 'approved', 'rejected', 'cancelled', 'completed');
create type actor_type      as enum ('customer', 'staff', 'system');
create type message_role    as enum ('user', 'assistant', 'tool');
create type proposal_status as enum ('pending', 'approved', 'rejected', 'expired', 'failed');

-- Objects whose expressions compare these columns to text must be dropped first
-- and recreated after the type change.
alter table orders drop constraint ck_delivery_has_address;
drop index uq_one_pending_proposal;

-- The old CHECK constraints become redundant once the type itself limits the values.
alter table dishes              drop constraint dishes_unit_check,
                                drop constraint dishes_kashrut_check;
alter table dish_allergens      drop constraint dish_allergens_status_check;
alter table time_slots          drop constraint time_slots_fulfillment_check;
alter table orders              drop constraint orders_status_check,
                                drop constraint orders_fulfillment_check;
alter table order_events        drop constraint order_events_actor_type_check;
alter table ai_messages         drop constraint ai_messages_role_check;
alter table ai_change_proposals drop constraint ai_change_proposals_status_check;

-- Text defaults cannot be cast automatically, so drop and restore them around the change.
alter table orders              alter column status drop default;
alter table ai_change_proposals alter column status drop default;

alter table dishes
  alter column unit    type dish_unit using unit::dish_unit,
  alter column kashrut type kashrut   using kashrut::kashrut;

alter table dish_allergens
  alter column status type allergen_status using status::allergen_status;

alter table time_slots
  alter column fulfillment type fulfillment using fulfillment::fulfillment;

alter table orders
  alter column status      type order_status using status::order_status,
  alter column fulfillment type fulfillment  using fulfillment::fulfillment;

alter table order_items
  alter column snapshot_kashrut type kashrut   using snapshot_kashrut::kashrut,
  alter column snapshot_unit    type dish_unit using snapshot_unit::dish_unit;

alter table order_events
  alter column from_status type order_status using from_status::order_status,
  alter column to_status   type order_status using to_status::order_status,
  alter column actor_type  type actor_type   using actor_type::actor_type;

alter table ai_messages
  alter column role type message_role using role::message_role;

alter table ai_change_proposals
  alter column status type proposal_status using status::proposal_status;

alter table orders              alter column status set default 'draft';
alter table ai_change_proposals alter column status set default 'pending';

alter table orders add constraint ck_delivery_has_address check (
  fulfillment <> 'delivery' or (city is not null and delivery_address is not null));

-- At most one pending suggestion per order
create unique index uq_one_pending_proposal on ai_change_proposals (order_id) where status = 'pending';
