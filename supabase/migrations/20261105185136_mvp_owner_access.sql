-- Align fresh and upgraded projects with the single-owner MVP. No rows are deleted.
DO $owner_access$
DECLARE t text; p record; seq text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','addresses','events','orders','order_items',
    'dishes','dish_categories','dish_dietary','allergens','dish_allergens',
    'delivery_zones','time_slots','blocked_dates'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    FOR p IN SELECT policyname FROM pg_policies WHERE schemaname='public' AND tablename=t LOOP
      EXECUTE format('DROP POLICY %I ON public.%I',p.policyname,t);
    END LOOP;
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated',t);
    EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON public.%I TO authenticated',t);
    EXECUTE format('CREATE POLICY catering_owner ON public.%I FOR ALL TO authenticated
      USING ((SELECT auth.jwt()->''app_metadata''->>''role'')=''catering_owner'')
      WITH CHECK ((SELECT auth.jwt()->''app_metadata''->>''role'')=''catering_owner'')',t);
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name=t AND column_name='id') THEN
      seq:=pg_get_serial_sequence('public.'||t,'id');
      IF seq IS NOT NULL THEN
        EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC,anon,authenticated',seq);
        EXECUTE format('GRANT USAGE ON SEQUENCE %s TO authenticated',seq);
      END IF;
    END IF;
  END LOOP;
  FOREACH t IN ARRAY ARRAY['order_submissions','ai_conversations','ai_messages','ai_change_proposals'] LOOP
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated',t);
  END LOOP;
  -- Old course operations remain intact but are not available to the MVP browser.
  FOREACH t IN ARRAY ARRAY['employees','deliveries','payments','equipment_items',
    'equipment_movements','ingredients','ingredient_batches','ingredient_movements',
    'order_payment_summary','equipment_stock','equipment_out_by_order',
    'ingredient_batch_stock','ingredient_stock'] LOOP
    IF to_regclass('public.'||t) IS NOT NULL THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,anon,authenticated',t);
      IF EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname='supabase_realtime'
                 AND schemaname='public' AND tablename=t) THEN
        EXECUTE format('ALTER PUBLICATION supabase_realtime DROP TABLE public.%I',t);
      END IF;
    END IF;
  END LOOP;
END;
$owner_access$;

-- Keep storage paths compatible with existing dish images while narrowing writes to owner.
DROP POLICY IF EXISTS catering_images_read ON storage.objects;
DROP POLICY IF EXISTS catering_images_insert ON storage.objects;
DROP POLICY IF EXISTS catering_images_update ON storage.objects;
DROP POLICY IF EXISTS catering_images_delete ON storage.objects;
CREATE POLICY catering_images_read ON storage.objects FOR SELECT TO authenticated
USING (bucket_id='dish-images' AND (SELECT auth.jwt()->'app_metadata'->>'role')='catering_owner');
CREATE POLICY catering_images_insert ON storage.objects FOR INSERT TO authenticated
WITH CHECK (bucket_id='dish-images' AND (SELECT auth.jwt()->'app_metadata'->>'role')='catering_owner'
 AND split_part(name,'/',1)='dishes'
 AND EXISTS (SELECT 1 FROM public.dishes d WHERE d.legacy_code=split_part(name,'/',2)));
CREATE POLICY catering_images_update ON storage.objects FOR UPDATE TO authenticated
USING (bucket_id='dish-images' AND (SELECT auth.jwt()->'app_metadata'->>'role')='catering_owner')
WITH CHECK (bucket_id='dish-images' AND (SELECT auth.jwt()->'app_metadata'->>'role')='catering_owner'
 AND split_part(name,'/',1)='dishes'
 AND EXISTS (SELECT 1 FROM public.dishes d WHERE d.legacy_code=split_part(name,'/',2)));
CREATE POLICY catering_images_delete ON storage.objects FOR DELETE TO authenticated
USING (bucket_id='dish-images' AND (SELECT auth.jwt()->'app_metadata'->>'role')='catering_owner');
