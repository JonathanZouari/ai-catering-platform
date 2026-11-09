-- Auth roles + RLS, image storage for dishes, and realtime.
--
-- Roles: Supabase Auth users are customers by default. The business owner is a user whose
-- app_metadata.role = 'owner'. app_metadata can only be set server-side (service role), unlike
-- user_metadata, which users can edit themselves, so it is safe to authorize on.
--
-- Writes to orders, order_items and events stay with the FastAPI backend (service role), because
-- prices, quantities and order state are backend-authoritative (ADR-0003). Clients only read.

-- ---------------------------------------------------------------------------------------------
-- Link customers to Auth users
-- ---------------------------------------------------------------------------------------------
alter table public.customers
  add column auth_user_id uuid unique references auth.users (id) on delete set null;

alter table public.dishes add column image_path text;  -- object path inside the dish-images bucket

-- ---------------------------------------------------------------------------------------------
-- Owner check (reads the JWT only, so SECURITY INVOKER is enough)
-- ---------------------------------------------------------------------------------------------
create function public.is_owner()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select coalesce((select auth.jwt()) -> 'app_metadata' ->> 'role', '') = 'owner';
$$;

-- ---------------------------------------------------------------------------------------------
-- Data API grants (RLS below decides which rows)
-- ---------------------------------------------------------------------------------------------
grant select on public.dish_categories, public.dishes to anon, authenticated;
grant insert, update, delete on public.dish_categories, public.dishes to authenticated;
grant select, insert, update on public.customers to authenticated;
grant select on public.events, public.orders, public.order_items to authenticated;

-- ---------------------------------------------------------------------------------------------
-- RLS policies (RLS is already enabled on every table)
-- ---------------------------------------------------------------------------------------------

-- Menu: owner sees everything (including hidden dishes) and manages it.
create policy "owner reads all categories" on public.dish_categories
  for select to authenticated using ((select public.is_owner()));
create policy "owner inserts categories" on public.dish_categories
  for insert to authenticated with check ((select public.is_owner()));
create policy "owner updates categories" on public.dish_categories
  for update to authenticated
  using ((select public.is_owner())) with check ((select public.is_owner()));
create policy "owner deletes categories" on public.dish_categories
  for delete to authenticated using ((select public.is_owner()));

create policy "owner reads all dishes" on public.dishes
  for select to authenticated using ((select public.is_owner()));
create policy "owner inserts dishes" on public.dishes
  for insert to authenticated with check ((select public.is_owner()));
create policy "owner updates dishes" on public.dishes
  for update to authenticated
  using ((select public.is_owner())) with check ((select public.is_owner()));
create policy "owner deletes dishes" on public.dishes
  for delete to authenticated using ((select public.is_owner()));

-- Customers: own profile only; the owner can read all.
create policy "read own customer profile" on public.customers
  for select to authenticated
  using (auth_user_id = (select auth.uid()) or (select public.is_owner()));
create policy "create own customer profile" on public.customers
  for insert to authenticated with check (auth_user_id = (select auth.uid()));
create policy "update own customer profile" on public.customers
  for update to authenticated
  using (auth_user_id = (select auth.uid()))
  with check (auth_user_id = (select auth.uid()));

-- Events and orders: read your own (or everything as owner). Writes go through the backend.
create policy "read own events" on public.events
  for select to authenticated
  using (
    (select public.is_owner())
    or customer_id in (select id from public.customers where auth_user_id = (select auth.uid()))
  );

create policy "read own orders" on public.orders
  for select to authenticated
  using (
    (select public.is_owner())
    or customer_id in (select id from public.customers where auth_user_id = (select auth.uid()))
  );

-- Order items inherit visibility from orders (the subquery is itself filtered by orders' RLS).
create policy "read items of visible orders" on public.order_items
  for select to authenticated
  using (exists (select 1 from public.orders o where o.id = order_items.order_id));

-- ---------------------------------------------------------------------------------------------
-- Storage: public bucket for dish photos, owner-only writes
-- ---------------------------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'dish-images', 'dish-images', true, 5242880,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do nothing;

create policy "dish images are public" on storage.objects
  for select to anon, authenticated using (bucket_id = 'dish-images');
create policy "owner uploads dish images" on storage.objects
  for insert to authenticated
  with check (bucket_id = 'dish-images' and (select public.is_owner()));
create policy "owner replaces dish images" on storage.objects
  for update to authenticated
  using (bucket_id = 'dish-images' and (select public.is_owner()))
  with check (bucket_id = 'dish-images' and (select public.is_owner()));
create policy "owner deletes dish images" on storage.objects
  for delete to authenticated
  using (bucket_id = 'dish-images' and (select public.is_owner()));

-- ---------------------------------------------------------------------------------------------
-- Realtime: broadcast row changes (RLS still filters who receives what)
-- ---------------------------------------------------------------------------------------------
alter publication supabase_realtime add table public.dishes, public.orders, public.order_items;
alter table public.orders replica identity full;
alter table public.dishes replica identity full;
