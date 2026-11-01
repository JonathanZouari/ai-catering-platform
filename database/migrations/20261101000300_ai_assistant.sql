-- Phase 7: AI chat tables become ordinary tenant tables. They were created
-- empty in the initial schema and nothing has written to them yet.

alter table ai_conversations
    add column caterer_id uuid not null references caterers (id) on delete cascade,
    drop constraint ai_conversations_order_id_fkey,
    add constraint ai_conversations_order_fkey
        foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade,
    add constraint ai_conversations_order_id_key unique (order_id),
    add constraint ai_conversations_caterer_id_id_key unique (caterer_id, id);

alter table ai_messages
    add column caterer_id uuid not null references caterers (id) on delete cascade,
    drop constraint ai_messages_conversation_id_fkey,
    add constraint ai_messages_conversation_fkey
        foreign key (caterer_id, conversation_id)
        references ai_conversations (caterer_id, id) on delete cascade;

alter table ai_change_proposals
    add column caterer_id uuid not null references caterers (id) on delete cascade,
    add column rationale text not null,
    drop constraint ai_change_proposals_order_id_fkey,
    add constraint ai_change_proposals_order_fkey
        foreign key (caterer_id, order_id) references orders (caterer_id, id) on delete cascade;

-- Monthly AI messages per caterer (OPEN_DECISIONS #16).
create table ai_usage (
    caterer_id uuid not null references caterers (id) on delete cascade,
    month date not null,
    message_count int not null default 0,
    primary key (caterer_id, month)
);
alter table ai_usage enable row level security;
