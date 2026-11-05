-- Access model
--   owner    : auth user with app_metadata.role = 'owner' (app_metadata is server-controlled; never user_metadata).
--   customer : any other signed-in user; sees only the orders linked to their customers row (customers.auth_user_id).
--   anon     : reads the active catalog (menu, zones, slots, blocked dates, settings). Nothing else.
--   backend  : service role, bypasses RLS (guest checkout by order uuid, AI proposal execution).

-- Grants (RLS decides rows; grants decide whether the Data API can touch the table at all).
revoke all on all tables in schema public from anon, authenticated;
grant select on dish_categories, dishes, allergens, dish_allergens, delivery_zones, time_slots, blocked_dates, settings
    to anon, authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant usage on all sequences in schema public to authenticated;

-- Catalog: public read of active rows (owner also sees inactive ones).
create policy "catalog read" on dish_categories for select to anon, authenticated
    using (is_active or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "catalog read" on dishes for select to anon, authenticated
    using (is_available or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "catalog read" on delivery_zones for select to anon, authenticated
    using (is_active or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "catalog read" on time_slots for select to anon, authenticated
    using (is_active or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "catalog read" on allergens      for select to anon, authenticated using (true);
create policy "catalog read" on dish_allergens for select to anon, authenticated using (true);
create policy "catalog read" on blocked_dates  for select to anon, authenticated using (true);
create policy "catalog read" on settings       for select to anon, authenticated using (true);

-- Customer-scoped reads.
create policy "own or owner" on customers for select to authenticated
    using (auth_user_id = (select auth.uid()) or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');

create policy "own or owner" on orders for select to authenticated
    using (
        customer_id in (select id from customers where auth_user_id = (select auth.uid()))
        or ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');

-- Child rows follow the order: the subquery runs under orders' own RLS, so it only matches visible orders.
create policy "via order" on events for select to authenticated
    using (exists (select 1 from orders o where o.event_id = events.id));
create policy "via order" on order_items for select to authenticated
    using (exists (select 1 from orders o where o.id = order_items.order_id));
create policy "via order" on ai_messages for select to authenticated
    using (exists (select 1 from orders o where o.id = ai_messages.order_id));
create policy "via order" on ai_change_proposals for select to authenticated
    using (exists (select 1 from orders o where o.id = ai_change_proposals.order_id));

-- Writes: owner only, on every table. Customers write through the backend (service role).
do $$
declare t text;
begin
    foreach t in array array[
        'settings','dish_categories','dishes','allergens','dish_allergens','delivery_zones','time_slots',
        'blocked_dates','customers','events','orders','order_items','ai_messages','ai_change_proposals']
    loop
        execute format($f$create policy "owner insert" on %I for insert to authenticated
            with check (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')$f$, t);
        execute format($f$create policy "owner update" on %I for update to authenticated
            using (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')
            with check (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')$f$, t);
        execute format($f$create policy "owner delete" on %I for delete to authenticated
            using (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')$f$, t);
    end loop;
end $$;

-- Storage: public bucket for dish photos. Anyone can view by URL; only the owner can upload, replace or delete.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do nothing;

-- Upsert needs INSERT + SELECT + UPDATE.
create policy "owner select dish images" on storage.objects for select to authenticated
    using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner insert dish images" on storage.objects for insert to authenticated
    with check (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner update dish images" on storage.objects for update to authenticated
    using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')
    with check (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner delete dish images" on storage.objects for delete to authenticated
    using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');

-- Realtime: Postgres changes are filtered by the same RLS policies, so each viewer only receives rows they may read.
alter publication supabase_realtime add table orders, order_items, ai_messages, ai_change_proposals, dishes, time_slots;
