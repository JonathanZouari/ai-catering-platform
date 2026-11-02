-- Change proposals on orders (OPEN_DECISIONS #6, decided 2026-11-02).
-- One table for both proposers: the owner (orders awaiting approval, this slice) and the AI
-- assistant (drafts, Phase 4). Replaces the planned ai_change_proposals.

create table order_proposals (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null references orders(id) on delete cascade,
  proposed_by text not null check (proposed_by in ('owner', 'assistant')),
  base_order_version int not null, -- must equal orders.version when accepted
  changes jsonb not null, -- [{op, dish_id, name, from_quantity, to_quantity}]
  lines jsonb not null, -- full proposed item list with frozen prices
  price_before numeric(10, 2) not null,
  price_after numeric(10, 2) not null,
  note text, -- from the proposer, shown to the customer
  status text not null default 'pending'
    check (status in ('pending', 'accepted', 'declined', 'cancelled', 'expired')),
  customer_note text, -- reason when declining
  created_at timestamptz not null default now(),
  decided_at timestamptz
);
create index order_proposals_order_id_idx on order_proposals (order_id);
create unique index order_proposals_one_pending on order_proposals (order_id) where status = 'pending';

alter table order_proposals enable row level security;
