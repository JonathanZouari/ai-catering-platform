-- The pickup/delivery slot an order uses, so capacity can be counted per slot per event date
-- (OPEN_DECISIONS #5). Deleting a slot keeps its orders; they just lose the link.

alter table orders
  add column slot_id uuid references time_slots(id) on delete set null;

create index orders_slot_id_idx on orders (slot_id);
