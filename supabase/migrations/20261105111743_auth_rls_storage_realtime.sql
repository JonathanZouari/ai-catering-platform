-- Who can see and change what, dish-image storage, and live order updates.
--
-- Roles (Supabase):
--   anon           visitor who is not logged in
--   authenticated  anyone logged in; is_staff() / my_customer_id() decide what they are
--   service_role   the FastAPI backend; bypasses RLS (prices, submissions, AI changes go through it)
--
-- Staff  = a row in staff_users with is_active = true (never user_metadata, which users can edit).
-- Customer = a customers row whose auth_user_id is the logged-in user.

-- Helper functions ------------------------------------------------------------
-- In a schema the Data API does not expose. security definer so the lookup
-- itself is not blocked by RLS on staff_users / customers; each one only ever
-- answers about the caller (auth.uid()).

create schema if not exists private;
grant usage on schema private to anon, authenticated;

create or replace function private.is_staff()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.staff_users
    where id = (select auth.uid()) and is_active
  );
$$;

create or replace function private.my_customer_id()
returns uuid
language sql stable security definer set search_path = ''
as $$
  select id from public.customers where auth_user_id = (select auth.uid());
$$;

revoke all on function private.is_staff(), private.my_customer_id() from public;
grant execute on function private.is_staff(), private.my_customer_id() to anon, authenticated;

-- Grants: which tables each role may touch at all (RLS then filters rows) ---

revoke all on all tables in schema public from anon, authenticated;

-- The public menu and delivery info can be read without logging in.
grant select on settings, categories, dishes, allergens, dish_allergens,
                delivery_zones, zone_cities, time_slots
  to anon;

grant select, insert, update, delete on all tables in schema public to authenticated;

-- Turn on RLS everywhere ------------------------------------------------------

alter table settings            enable row level security;
alter table staff_users         enable row level security;
alter table categories          enable row level security;
alter table allergens           enable row level security;
alter table delivery_zones      enable row level security;
alter table time_slots          enable row level security;
alter table calendar_overrides  enable row level security;
alter table customers           enable row level security;
alter table dishes              enable row level security;
alter table zone_cities         enable row level security;
alter table dish_allergens      enable row level security;
alter table orders              enable row level security;
alter table order_items         enable row level security;
alter table order_events        enable row level security;
alter table ai_conversations    enable row level security;
alter table ai_messages         enable row level security;
alter table ai_change_proposals enable row level security;

-- Staff manage everything -----------------------------------------------------

do $$
declare t text;
begin
  foreach t in array array[
    'settings','staff_users','categories','allergens','delivery_zones','time_slots',
    'calendar_overrides','customers','dishes','zone_cities','dish_allergens','orders',
    'order_items','order_events','ai_conversations','ai_messages','ai_change_proposals']
  loop
    execute format(
      'create policy "staff manage %1$s" on public.%1$I for all to authenticated
         using ((select private.is_staff())) with check ((select private.is_staff()))', t);
  end loop;
end $$;

-- Public menu (visitors and customers) ----------------------------------------

create policy "anyone reads settings" on settings
  for select to anon, authenticated using (true);
create policy "anyone reads active categories" on categories
  for select to anon, authenticated using (is_active);
create policy "anyone reads available dishes" on dishes
  for select to anon, authenticated using (is_available);
create policy "anyone reads allergens" on allergens
  for select to anon, authenticated using (true);
create policy "anyone reads dish allergens" on dish_allergens
  for select to anon, authenticated using (true);
create policy "anyone reads active zones" on delivery_zones
  for select to anon, authenticated using (is_active);
create policy "anyone reads delivery cities" on zone_cities
  for select to anon, authenticated using (true);
create policy "anyone reads active time slots" on time_slots
  for select to anon, authenticated using (is_active);
-- calendar_overrides stays staff-only: its reason column is an internal note.
-- The backend tells customers which dates are free.

-- Staff can see their own row (the admin uses it to check "am I staff?") ------

create policy "staff read own row" on staff_users
  for select to authenticated using (id = (select auth.uid()));

-- Customers see only their own data -------------------------------------------
-- Customers do not write orders directly: submitting, pricing and AI changes go
-- through the backend so totals and capacity are always computed server-side.

create policy "customer reads own profile" on customers
  for select to authenticated using (auth_user_id = (select auth.uid()));
create policy "customer updates own profile" on customers
  for update to authenticated
  using (auth_user_id = (select auth.uid()))
  with check (auth_user_id = (select auth.uid()));

create policy "customer reads own orders" on orders
  for select to authenticated using (customer_id = (select private.my_customer_id()));

create policy "customer reads own order items" on order_items
  for select to authenticated using (
    order_id in (select id from public.orders where customer_id = (select private.my_customer_id())));

create policy "customer reads own order history" on order_events
  for select to authenticated using (
    order_id in (select id from public.orders where customer_id = (select private.my_customer_id())));

create policy "customer reads own chats" on ai_conversations
  for select to authenticated using (
    order_id in (select id from public.orders where customer_id = (select private.my_customer_id())));

create policy "customer reads own chat messages" on ai_messages
  for select to authenticated using (
    conversation_id in (
      select c.id from public.ai_conversations c
      join public.orders o on o.id = c.order_id
      where o.customer_id = (select private.my_customer_id())));

create policy "customer reads own suggestions" on ai_change_proposals
  for select to authenticated using (
    order_id in (select id from public.orders where customer_id = (select private.my_customer_id())));

-- Dish images -------------------------------------------------------------------
-- Public bucket: anyone can view an image by its URL. Only staff upload, replace
-- (upsert needs insert + select + update) or delete.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880,
        array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

create policy "staff read dish images" on storage.objects
  for select to authenticated
  using (bucket_id = 'dish-images' and (select private.is_staff()));
create policy "staff upload dish images" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'dish-images' and (select private.is_staff()));
create policy "staff replace dish images" on storage.objects
  for update to authenticated
  using (bucket_id = 'dish-images' and (select private.is_staff()))
  with check (bucket_id = 'dish-images' and (select private.is_staff()));
create policy "staff delete dish images" on storage.objects
  for delete to authenticated
  using (bucket_id = 'dish-images' and (select private.is_staff()));

-- Live order updates ------------------------------------------------------------
-- Realtime respects the select policies above: staff get every order,
-- a customer only their own.

alter publication supabase_realtime add table public.orders, public.order_events;
