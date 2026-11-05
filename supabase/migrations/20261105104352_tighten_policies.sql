-- Advisor fixes: one SELECT policy per table (no overlapping permissive policies), and no
-- anonymous grants on private tables.

drop policy "menu categories are public" on public.dish_categories;
drop policy "owner reads all categories" on public.dish_categories;
create policy "read menu categories" on public.dish_categories
  for select to anon, authenticated
  using (is_active or (select public.is_owner()));

drop policy "available dishes are public" on public.dishes;
drop policy "owner reads all dishes" on public.dishes;
create policy "read menu dishes" on public.dishes
  for select to anon, authenticated
  using (is_available or (select public.is_owner()));

revoke all on public.customers, public.events, public.orders, public.order_items from anon;
