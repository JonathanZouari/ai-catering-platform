-- Link customers to Supabase Auth users.
alter table customers add column auth_user_id uuid unique references auth.users(id) on delete set null;

-- Admin = app_metadata.role 'admin' (app_metadata is not user-editable, unlike user_metadata).
-- Data API grants; RLS below decides which rows.
grant usage on schema public to anon, authenticated;
grant select on dish_categories, dishes, dish_dietary, allergens, dish_allergens, delivery_zones, time_slots, blocked_dates to anon;
grant select, insert, update, delete on all tables in schema public to authenticated;

-- Public catalog: anyone reads; only admin writes.
do $$
declare t text;
begin
  foreach t in array array['dish_categories','dishes','dish_dietary','allergens','dish_allergens','delivery_zones','time_slots','blocked_dates'] loop
    execute format('create policy "%1$s public read" on %1$I for select to anon, authenticated using (true)', t);
  end loop;
  -- admin full access on every table
  foreach t in array array['customers','events','dish_categories','dishes','dish_dietary','allergens','dish_allergens','delivery_zones','time_slots','blocked_dates','orders','order_items','ai_conversations','ai_messages','ai_change_proposals'] loop
    execute format($f$create policy "%1$s admin all" on %1$I for all to authenticated
      using ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin')
      with check ((select auth.jwt() -> 'app_metadata' ->> 'role') = 'admin')$f$, t);
  end loop;
end $$;

-- Customers: own row.
create policy "customers own select" on customers for select to authenticated using (auth_user_id = (select auth.uid()));
create policy "customers own insert" on customers for insert to authenticated with check (auth_user_id = (select auth.uid()));
create policy "customers own update" on customers for update to authenticated
  using (auth_user_id = (select auth.uid())) with check (auth_user_id = (select auth.uid()));

-- Events and orders: through own customer. Orders are editable only while draft.
create policy "events own all" on events for all to authenticated
  using (customer_id in (select id from customers where auth_user_id = (select auth.uid())))
  with check (customer_id in (select id from customers where auth_user_id = (select auth.uid())));
create policy "orders own select" on orders for select to authenticated
  using (customer_id in (select id from customers where auth_user_id = (select auth.uid())));
create policy "orders own insert" on orders for insert to authenticated
  with check (status = 'draft' and customer_id in (select id from customers where auth_user_id = (select auth.uid())));
create policy "orders own update draft" on orders for update to authenticated
  using (status = 'draft' and customer_id in (select id from customers where auth_user_id = (select auth.uid())))
  with check (customer_id in (select id from customers where auth_user_id = (select auth.uid())));

-- Order items / AI data: through own order.
create policy "order_items own select" on order_items for select to authenticated
  using (order_id in (select id from orders));
create policy "order_items own write draft" on order_items for all to authenticated
  using (order_id in (select id from orders where status = 'draft'))
  with check (order_id in (select id from orders where status = 'draft'));
create policy "ai_conversations own" on ai_conversations for select to authenticated using (order_id in (select id from orders));
create policy "ai_messages own" on ai_messages for select to authenticated
  using (conversation_id in (select id from ai_conversations));
create policy "ai_proposals own select" on ai_change_proposals for select to authenticated using (order_id in (select id from orders));

-- Indexes the policies rely on.
create index idx_customers_auth_user on customers(auth_user_id);
create index idx_events_customer on events(customer_id);
create index idx_order_items_order on order_items(order_id);
create index idx_ai_messages_conv on ai_messages(conversation_id);
create index idx_ai_proposals_order on ai_change_proposals(order_id);

-- Realtime (respects RLS for authenticated subscribers; anon gets catalog changes only).
alter table orders replica identity full;
alter table ai_change_proposals replica identity full;
alter publication supabase_realtime add table orders, order_items, ai_change_proposals, ai_messages, dishes;
