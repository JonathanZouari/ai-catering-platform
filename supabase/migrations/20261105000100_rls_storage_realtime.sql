-- Row-level security, the dish-photo bucket, and Realtime on orders.
--
-- The FastAPI backend connects as a privileged role and does every write, so prices and
-- order state stay computed on the server (ADR 0003). Through the Supabase Data API and
-- Realtime, a logged-in caterer can only READ its own caterer's rows. Anonymous users can
-- read only the shared allergen list. Customers' private links are checked by the backend.

-- ---------------------------------------------------------------------------------------
-- Who is asking: the caterer of the logged-in Supabase user, or null.
-- Kept out of the exposed "public" schema so it can't be called as an RPC.
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create function private.current_caterer_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
    select cu.caterer_id
    from public.caterer_users cu
    where cu.auth_user_id = (select auth.uid())
$$;
revoke all on function private.current_caterer_id() from public;
grant execute on function private.current_caterer_id() to authenticated;

-- ---------------------------------------------------------------------------------------
-- The Data API may read, never write. RLS below narrows the reads to one caterer.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke all on all functions in schema public from anon, authenticated;
grant select on all tables in schema public to authenticated;
grant select on allergens to anon;

-- Tables created later don't silently become writable through the API.
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke all on functions from anon, authenticated;

-- ---------------------------------------------------------------------------------------
alter table caterers enable row level security;
alter table caterer_users enable row level security;
alter table customers enable row level security;
alter table events enable row level security;
alter table dish_categories enable row level security;
alter table dishes enable row level security;
alter table dish_dietary enable row level security;
alter table allergens enable row level security;
alter table dish_allergens enable row level security;
alter table delivery_zones enable row level security;
alter table time_slots enable row level security;
alter table blocked_dates enable row level security;
alter table quantity_rules enable row level security;
alter table orders enable row level security;
alter table order_items enable row level security;
alter table ai_conversations enable row level security;
alter table ai_messages enable row level security;
alter table ai_change_proposals enable row level security;
alter table ai_usage enable row level security;

-- (select ...) around the helper makes Postgres run it once per query, not once per row.
create policy "caterer reads itself" on caterers
    for select to authenticated using (id = (select private.current_caterer_id()));

create policy "caterer reads own rows" on caterer_users
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on customers
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on events
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on dish_categories
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on dishes
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on delivery_zones
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on time_slots
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on blocked_dates
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on orders
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on order_items
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on ai_conversations
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on ai_messages
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on ai_change_proposals
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));
create policy "caterer reads own rows" on ai_usage
    for select to authenticated using (caterer_id = (select private.current_caterer_id()));

-- Platform defaults (null caterer) plus the caterer's own overrides.
create policy "caterer reads defaults and own rules" on quantity_rules
    for select to authenticated
    using (caterer_id is null or caterer_id = (select private.current_caterer_id()));

-- These hang off a dish, so they follow the dish's caterer.
create policy "caterer reads own dishes" on dish_dietary
    for select to authenticated
    using (exists (
        select 1 from dishes d
        where d.id = dish_id and d.caterer_id = (select private.current_caterer_id())
    ));
create policy "caterer reads own dishes" on dish_allergens
    for select to authenticated
    using (exists (
        select 1 from dishes d
        where d.id = dish_id and d.caterer_id = (select private.current_caterer_id())
    ));

create policy "everyone reads allergens" on allergens
    for select to anon, authenticated using (true);

-- ---------------------------------------------------------------------------------------
-- Storage: the bucket the app already uploads to (core/storage.py). Paths start with the
-- caterer id. Public to read, so menu photos load without a token. No storage.objects
-- policies for insert, update or delete, so only the backend's service role can write.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'caterer-assets',
    'caterer-assets',
    true,
    5 * 1024 * 1024,
    array['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
);

-- ---------------------------------------------------------------------------------------
-- Realtime: the caterer's dashboard hears new orders and status changes. Realtime applies
-- the RLS policies above, so each caterer only receives its own orders.
alter publication supabase_realtime add table orders;
