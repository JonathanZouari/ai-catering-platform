-- Schema consistency (review of the dev database, 2026-11-06).

-- 1. order_proposals.status: a Postgres enum like orders.status, instead of text + check.
create type proposal_status as enum ('pending', 'accepted', 'declined', 'cancelled', 'expired');
drop index order_proposals_one_pending; -- its predicate compares text; rebuilt below
alter table order_proposals drop constraint order_proposals_status_check;
alter table order_proposals alter column status drop default;
alter table order_proposals
  alter column status type proposal_status using status::proposal_status;
alter table order_proposals alter column status set default 'pending';
create unique index order_proposals_one_pending on order_proposals (order_id) where status = 'pending';

-- 2. orders.delivery_zone_id duplicated what delivery_city implies (via delivery_zone_cities)
-- and nothing read it. The frozen fee stays in delivery_fee; the city stays as typed, so
-- later zone changes never rewrite past orders.
alter table orders drop column delivery_zone_id;

-- 3. ai_messages: uuid id like every other table. The bigint identity also kept the message
-- order; position now does (a turn's messages share one transaction, so created_at ties).
alter table ai_messages add column position int;
update ai_messages m
set position = r.n
from (
  select id, row_number() over (partition by conversation_id order by id) as n from ai_messages
) r
where m.id = r.id;
alter table ai_messages alter column position set not null;
alter table ai_messages add column new_id uuid not null default gen_random_uuid();
alter table ai_messages drop constraint ai_messages_pkey;
alter table ai_messages drop column id;
alter table ai_messages rename column new_id to id;
alter table ai_messages add primary key (id);
alter table ai_messages
  add constraint ai_messages_conversation_position unique (conversation_id, position);
