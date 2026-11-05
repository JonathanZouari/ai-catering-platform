-- Access rules (RLS), Data API grants, dish-image upload rules and realtime.
--
-- Who can do what:
--   anyone (anon)      read the menu: categories, dishes, diet, allergens, zones, time slots, blocked dates
--   signed-in customer read their own profile, events, orders, items, AI chat and proposals;
--                      edit their own name and phone
--   owner              read and write everything; upload dish images
--   backend            service role, bypasses RLS: creates orders, prices them, runs the AI agent
-- Owner = app_metadata.role 'owner' (set only with the service role; users cannot edit app_metadata).

-- ---------- Data API grants (new projects do not expose tables by default) ----------
grant usage on schema public to anon, authenticated;

grant select on dish_categories, dishes, dish_dietary, allergens, dish_allergens,
  delivery_zones, time_slots, blocked_dates to anon, authenticated;

grant select, insert, update, delete on all tables in schema public to authenticated;

-- ---------- Menu: public read, owner writes ----------
do $$
declare t text;
begin
  foreach t in array array['dish_categories', 'dishes', 'dish_dietary', 'allergens', 'dish_allergens',
                           'delivery_zones', 'time_slots', 'blocked_dates']
  loop
    execute format('create policy "menu is public" on %I for select to anon, authenticated using (true)', t);
    execute format($p$create policy "owner manages" on %I for all to authenticated
      using (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')
      with check (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')$p$, t);
  end loop;
end $$;

-- ---------- Customer data: own rows read, owner everything ----------
do $$
declare t text;
begin
  foreach t in array array['customers', 'events', 'orders', 'order_items',
                           'ai_conversations', 'ai_messages', 'ai_change_proposals']
  loop
    execute format($p$create policy "owner manages" on %I for all to authenticated
      using (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')
      with check (((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')$p$, t);
  end loop;
end $$;

create policy "customer reads own profile" on customers for select to authenticated
  using (auth_user_id = (select auth.uid()));

create policy "customer edits own profile" on customers for update to authenticated
  using (auth_user_id = (select auth.uid()))
  with check (auth_user_id = (select auth.uid()));

create policy "customer reads own events" on events for select to authenticated
  using (customer_id in (select id from customers where auth_user_id = (select auth.uid())));

create policy "customer reads own orders" on orders for select to authenticated
  using (customer_id in (select id from customers where auth_user_id = (select auth.uid())));

create policy "customer reads own order items" on order_items for select to authenticated
  using (order_id in (select id from orders));  -- orders is already filtered by its own policy

create policy "customer reads own conversations" on ai_conversations for select to authenticated
  using (order_id in (select id from orders));

create policy "customer reads own messages" on ai_messages for select to authenticated
  using (conversation_id in (select id from ai_conversations));

create policy "customer reads own proposals" on ai_change_proposals for select to authenticated
  using (order_id in (select id from orders));

-- Customers may change only their name and phone, never auth_user_id or email.
revoke update on customers from authenticated;
grant update (full_name, phone) on customers to authenticated;

create index if not exists idx_customers_auth_user on customers(auth_user_id);

-- ---------- Dish images: public bucket for viewing, only the owner uploads ----------
-- Upsert (replacing a photo) needs insert + select + update.
create policy "owner reads dish images" on storage.objects for select to authenticated
  using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner uploads dish images" on storage.objects for insert to authenticated
  with check (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner replaces dish images" on storage.objects for update to authenticated
  using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner')
  with check (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');
create policy "owner deletes dish images" on storage.objects for delete to authenticated
  using (bucket_id = 'dish-images' and ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'owner');

-- ---------- Realtime: live updates, filtered by the same RLS rules ----------
alter publication supabase_realtime add table orders, order_items, ai_messages, ai_change_proposals, dishes;
