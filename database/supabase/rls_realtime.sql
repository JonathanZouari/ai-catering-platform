-- RLS, grants and Realtime for the dedicated `cateringproject` Supabase project ONLY.
-- Applied BY HAND (psql "$DATABASE_URL" -f database/supabase/rls_realtime.sql), after the
-- migrations. It is NOT in database/migrations/ because local and test Postgres have no `auth`
-- schema or `anon`/`authenticated` roles, and it must never run against any other project.
-- Safe to re-run.
--
-- Model: the FastAPI backend (privileged role) does every write and all price/state rules. The
-- browser only READS through PostgREST/Realtime with the user's JWT:
--   anon          menu + public logistics (active rows only); no orders
--   authenticated own customers/events/orders/order_items/order_ratings rows; same public reads
--   admin         read everything (app_metadata.role = 'admin', which users cannot edit)
-- Nobody gets direct writes: admin changes go through the backend's validated routes.
-- orders.access_token_hash is excluded from column grants and from the Realtime column list.

BEGIN;

-- Newer projects do not auto-grant; older ones over-grant. Start from nothing.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon, authenticated;

-- RLS on every table (the migrations already do this; schema_migrations is added here).
DO $$
DECLARE t text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

-- ---- grants: read-only, per table (orders by column, without access_token_hash)
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON allergens, dish_categories, dishes, dish_dietary, dish_allergens,
  delivery_zones, time_slots, blocked_dates TO anon, authenticated;
GRANT SELECT ON customers, events, order_items, order_ratings TO authenticated;
-- Admin-only tables still need a SELECT grant for the admin policy to apply.
GRANT SELECT ON quantity_rules, business_settings, notifications, order_files, geocode_cache,
  ai_conversations, ai_messages, ai_change_proposals TO authenticated;
DO $$
BEGIN
  EXECUTE (
    SELECT format('GRANT SELECT (%s) ON public.orders TO authenticated',
                  string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position))
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'orders' AND column_name <> 'access_token_hash'
  );
END $$;

-- Without any SELECT grant Realtime still tells anon that a row changed (an empty event with
-- "401"), which reveals order activity. With a grant and no anon policy, RLS drops the event.
GRANT SELECT (id) ON orders, order_items TO anon;

-- ---- policies (dropped and recreated so re-runs converge)
DO $$
DECLARE p record;
BEGIN
  FOR p IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'public' LOOP
    EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, p.tablename);
  END LOOP;
END $$;

-- Public reads. Dishes and categories stay readable when switched off: Realtime applies RLS to the
-- new row, so a filter here would hide the very event that takes a dish off the live menu.
-- The backend's catalog routes still hide them. No personal data lives in these tables.
CREATE POLICY public_read ON dish_categories FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read ON dishes FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read ON delivery_zones FOR SELECT TO anon, authenticated USING (is_active);
CREATE POLICY public_read ON time_slots FOR SELECT TO anon, authenticated USING (is_active);
CREATE POLICY public_read ON allergens FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read ON blocked_dates FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY public_read ON dish_dietary FOR SELECT TO anon, authenticated
  USING (EXISTS (SELECT 1 FROM dishes d WHERE d.id = dish_id AND d.is_available));
CREATE POLICY public_read ON dish_allergens FOR SELECT TO anon, authenticated
  USING (EXISTS (SELECT 1 FROM dishes d WHERE d.id = dish_id AND d.is_available));

-- A signed-in customer reads only their own rows (auth.uid() is wrapped so it is evaluated once).
CREATE POLICY own_row ON customers FOR SELECT TO authenticated
  USING (auth_user_id = (SELECT auth.uid()));
CREATE POLICY own_row ON orders FOR SELECT TO authenticated
  USING (customer_id IN (SELECT id FROM customers WHERE auth_user_id = (SELECT auth.uid())));
CREATE POLICY own_row ON events FOR SELECT TO authenticated
  USING (customer_id IN (SELECT id FROM customers WHERE auth_user_id = (SELECT auth.uid())));
CREATE POLICY own_row ON order_items FOR SELECT TO authenticated
  USING (order_id IN (SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id
                      WHERE c.auth_user_id = (SELECT auth.uid())));
CREATE POLICY own_row ON order_ratings FOR SELECT TO authenticated
  USING (order_id IN (SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id
                      WHERE c.auth_user_id = (SELECT auth.uid())));

-- Admin reads every table the role can select. app_metadata is server-controlled; user_metadata
-- is user-editable and is never consulted.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['allergens', 'dish_categories', 'dishes', 'dish_dietary', 'dish_allergens',
    'delivery_zones', 'time_slots', 'blocked_dates', 'customers', 'events', 'orders', 'order_items',
    'order_ratings', 'quantity_rules', 'business_settings', 'notifications', 'order_files',
    'geocode_cache', 'ai_conversations', 'ai_messages', 'ai_change_proposals'] LOOP
    EXECUTE format(
      $f$CREATE POLICY admin_read ON public.%I FOR SELECT TO authenticated
         USING (((SELECT auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin')$f$, t);
  END LOOP;
END $$;

-- ---- Realtime. orders is published with an explicit column list that leaves out the token hash.
DO $$
BEGIN
  EXECUTE (
    SELECT format(
      'ALTER PUBLICATION supabase_realtime SET TABLE public.order_items, public.dishes, '
      || 'public.dish_categories, public.orders (%s)',
      string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position))
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'orders' AND column_name <> 'access_token_hash'
  );
END $$;

COMMIT;
