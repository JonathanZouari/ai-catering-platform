-- AI ordering assistant (Phase 4, OPEN_DECISIONS #16 decided 2026-11-04: Anthropic Claude).
-- Assistant proposals reuse order_proposals (proposed_by = 'assistant', on drafts).

create table ai_conversations (
  id uuid primary key default gen_random_uuid(),
  order_id uuid not null unique references orders(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- Messages exactly as exchanged with the model, append-only; id keeps the order.
create table ai_messages (
  id bigint generated always as identity primary key,
  conversation_id uuid not null references ai_conversations(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content jsonb not null, -- API content blocks (text, thinking, tool_use, tool_result)
  customer_text text, -- the customer's own words; null for tool results and replies
  created_at timestamptz not null default now()
);
create index ai_messages_conversation_id_idx on ai_messages (conversation_id);

-- Messages a customer may send the assistant in any 24 hours, owner-editable.
alter table business_settings
  add column assistant_daily_limit int not null default 30
    check (assistant_daily_limit between 0 and 1000);

alter table ai_conversations enable row level security;
alter table ai_messages enable row level security;
