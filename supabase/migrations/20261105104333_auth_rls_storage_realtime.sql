-- Access model:
--   customer: a signed-in user linked by customers.auth_user_id. Reads the catalog and their own data.
--   admin:    a user with app_metadata.role = 'admin'. Only the service role can set app_metadata.
-- Prices and order status change only through the functions below, never by a direct client write.

create schema private;
grant usage on schema private to authenticated;

-- 1. Helpers
create function private.is_admin() returns boolean
language sql stable set search_path = '' as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role' = 'admin', false)
$$;

-- security definer: reads customers without re-entering the customers RLS policy.
create function private.current_customer_id() returns uuid
language sql stable security definer set search_path = '' as $$
  select id from public.customers where auth_user_id = auth.uid()
$$;

revoke execute on all functions in schema private from public;
grant execute on function private.is_admin() to authenticated;
grant execute on function private.current_customer_id() to authenticated;

-- 2. Every new customer account gets a customers row. full_name is display text only.
create function private.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(new.raw_app_meta_data ->> 'role', '') <> 'admin' then
    insert into public.customers (auth_user_id, full_name, email)
    values (new.id, coalesce(nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''), 'לקוח'), new.email);
  end if;
  return new;
end $$;
revoke execute on function private.handle_new_user() from public;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function private.handle_new_user();

-- 3. Table privileges. RLS decides which rows; these decide which operations can exist at all.
revoke all on all tables in schema public from anon;
revoke insert, update, delete, truncate on customers, events, orders, order_items,
  ai_conversations, ai_messages, ai_change_proposals from authenticated;
grant update (full_name, phone) on customers to authenticated;

-- 4. Catalog and logistics: every signed-in user reads, only the admin writes.
do $$
declare t text;
begin
  foreach t in array array['dish_categories', 'dishes', 'dish_dietary', 'allergens', 'dish_allergens',
                           'delivery_zones', 'time_slots', 'blocked_dates'] loop
    execute format('create policy "signed-in users read" on public.%I for select to authenticated using (true)', t);
    execute format('create policy "admin inserts" on public.%I for insert to authenticated with check ((select private.is_admin()))', t);
    execute format('create policy "admin updates" on public.%I for update to authenticated using ((select private.is_admin())) with check ((select private.is_admin()))', t);
    execute format('create policy "admin deletes" on public.%I for delete to authenticated using ((select private.is_admin()))', t);
  end loop;
end $$;

-- 5. Customer data: owner or admin reads. Only customers has a direct write, limited to two columns above.
create policy "owner or admin reads" on customers for select to authenticated
  using (auth_user_id = (select auth.uid()) or (select private.is_admin()));
create policy "owner updates" on customers for update to authenticated
  using (auth_user_id = (select auth.uid())) with check (auth_user_id = (select auth.uid()));

create policy "owner or admin reads" on events for select to authenticated
  using (customer_id = (select private.current_customer_id()) or (select private.is_admin()));
create policy "owner or admin reads" on orders for select to authenticated
  using (customer_id = (select private.current_customer_id()) or (select private.is_admin()));

create policy "owner or admin reads" on order_items for select to authenticated
  using ((select private.is_admin()) or exists (
    select 1 from public.orders o where o.id = order_id and o.customer_id = (select private.current_customer_id())));
create policy "owner or admin reads" on ai_conversations for select to authenticated
  using ((select private.is_admin()) or exists (
    select 1 from public.orders o where o.id = order_id and o.customer_id = (select private.current_customer_id())));
create policy "owner or admin reads" on ai_change_proposals for select to authenticated
  using ((select private.is_admin()) or exists (
    select 1 from public.orders o where o.id = order_id and o.customer_id = (select private.current_customer_id())));
create policy "owner or admin reads" on ai_messages for select to authenticated
  using ((select private.is_admin()) or exists (
    select 1 from public.ai_conversations c join public.orders o on o.id = c.order_id
    where c.id = conversation_id and o.customer_id = (select private.current_customer_id())));

-- 6. Order workflow. Totals are computed here from current dish prices; the client never sends a price.
-- ponytail: pricing lives in SQL until the FastAPI service layer exists (ADR-0002, ADR-0003), then move it there.
create function private.submit_order(payload jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  v_customer uuid := private.current_customer_id();
  v_tz constant text := 'Asia/Jerusalem';
  e jsonb := payload -> 'event';
  v_date date := (e ->> 'date')::date;
  v_fulfillment public.fulfillment_type := (e ->> 'fulfillment')::public.fulfillment_type;
  v_start time := split_part(e ->> 'slot', '-', 1)::time;
  v_end time := split_part(e ->> 'slot', '-', 2)::time;
  v_slot uuid;
  v_zone uuid;
  v_fee numeric(10,2) := 0;
  v_event uuid;
  v_order uuid;
  v_subtotal numeric(10,2);
  v_expected int;
  v_priced int;
begin
  if v_customer is null then
    raise exception 'לחשבון הזה אין פרופיל לקוח' using errcode = '42501';
  end if;
  if v_date <= (now() at time zone v_tz)::date then
    raise exception 'תאריך האירוע חייב להיות בעתיד';
  end if;
  if exists (select 1 from public.blocked_dates where date = v_date) then
    raise exception 'התאריך הזה סגור להזמנות';
  end if;

  select id into v_slot from public.time_slots
  where is_active and fulfillment_type = v_fulfillment and start_time = v_start and end_time = v_end
    and (weekday is null or weekday = extract(dow from v_date));
  if v_slot is null then
    raise exception 'חלון הזמן שנבחר אינו זמין';
  end if;

  if v_fulfillment = 'delivery' then
    select id, fee into v_zone, v_fee from public.delivery_zones
    where is_active and definition ->> 'city' = e ->> 'city';
    if v_zone is null then
      raise exception 'אין משלוחים לעיר שנבחרה';
    end if;
    if coalesce(trim(e ->> 'address'), '') = '' then
      raise exception 'חסרה כתובת למשלוח';
    end if;
  end if;

  select count(*) into v_expected from jsonb_array_elements(payload -> 'items');
  if v_expected = 0 then
    raise exception 'ההזמנה ריקה';
  end if;

  update public.customers
  set full_name = coalesce(nullif(trim(payload #>> '{contact,name}'), ''), full_name),
      phone = coalesce(nullif(trim(payload #>> '{contact,phone}'), ''), phone)
  where id = v_customer;

  insert into public.events (customer_id, event_type, event_date, adults, children,
                             vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)
  values (v_customer, e ->> 'type', v_date, (e ->> 'adults')::int, coalesce((e ->> 'children')::int, 0),
          coalesce((e ->> 'vegetarian')::int, 0), coalesce((e ->> 'vegan')::int, 0),
          coalesce((e ->> 'restricted')::int, 0), nullif(trim(e ->> 'notes'), ''))
  returning id into v_event;

  insert into public.orders (customer_id, event_id, fulfillment_type, requested_at, time_slot_id,
                             delivery_address, delivery_zone_id)
  values (v_customer, v_event, v_fulfillment, (v_date + v_start) at time zone v_tz, v_slot,
          nullif(trim(concat_ws(', ', e ->> 'address', e ->> 'city')), ''), v_zone)
  returning id into v_order;
  if v_fulfillment = 'pickup' then
    update public.orders set delivery_address = null where id = v_order;
  end if;

  insert into public.order_items (order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit,
                                  snapshot_unit_price, snapshot_line_total)
  select v_order, d.id, i.quantity, d.name, d.pricing_unit, d.unit_price, round(d.unit_price * i.quantity, 2)
  from jsonb_to_recordset(payload -> 'items') as i (dish_id uuid, quantity numeric)
  join public.dishes d on d.id = i.dish_id
  where d.is_available and i.quantity > 0 and i.quantity >= coalesce(d.min_quantity, 0);

  select count(*), sum(snapshot_line_total) into v_priced, v_subtotal
  from public.order_items where order_id = v_order;
  if v_priced <> v_expected then
    raise exception 'אחת המנות אינה זמינה יותר או שהכמות שלה אינה תקינה';
  end if;

  update public.orders
  set status = 'pending_approval', subtotal = v_subtotal, delivery_fee = v_fee,
      total = v_subtotal + v_fee, submitted_at = now(), version = version + 1
  where id = v_order;

  return jsonb_build_object('id', v_order, 'subtotal', v_subtotal, 'delivery_fee', v_fee,
                            'total', v_subtotal + v_fee, 'submitted_at', now());
end $$;

create function private.decide_order(order_id uuid, decision public.order_status, note text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_admin() then
    raise exception 'רק בעל העסק יכול להחליט על הזמנה' using errcode = '42501';
  end if;
  if decision not in ('approved', 'rejected') then
    raise exception 'החלטה לא תקינה';
  end if;
  update public.orders
  set status = decision, decided_at = now(), decision_note = nullif(trim(note), ''), version = version + 1
  where id = order_id and status = 'pending_approval';
  if not found then
    raise exception 'ההזמנה כבר טופלה או לא נמצאה' using errcode = 'P0002';
  end if;
end $$;

revoke execute on function private.submit_order(jsonb) from public;
revoke execute on function private.decide_order(uuid, public.order_status, text) from public;
grant execute on function private.submit_order(jsonb) to authenticated;
grant execute on function private.decide_order(uuid, public.order_status, text) to authenticated;

-- Thin invoker wrappers: the Data API exposes these, the privileged code stays in an unexposed schema.
create function public.submit_order(payload jsonb) returns jsonb
language sql set search_path = '' as $$ select private.submit_order(payload) $$;
create function public.decide_order(order_id uuid, decision public.order_status, note text default null) returns void
language sql set search_path = '' as $$ select private.decide_order(order_id, decision, note) $$;

revoke execute on function public.submit_order(jsonb) from public, anon;
revoke execute on function public.decide_order(uuid, public.order_status, text) from public, anon;
grant execute on function public.submit_order(jsonb) to authenticated;
grant execute on function public.decide_order(uuid, public.order_status, text) to authenticated;
revoke execute on function public.set_updated_at() from public, anon, authenticated;

-- 7. Dish images: public to read by URL, only the admin writes. Upsert needs select + insert + update.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg', 'image/png', 'image/webp']);

create policy "admin reads dish images" on storage.objects for select to authenticated
  using (bucket_id = 'dish-images' and (select private.is_admin()));
create policy "admin uploads dish images" on storage.objects for insert to authenticated
  with check (bucket_id = 'dish-images' and (select private.is_admin()));
create policy "admin updates dish images" on storage.objects for update to authenticated
  using (bucket_id = 'dish-images' and (select private.is_admin()))
  with check (bucket_id = 'dish-images' and (select private.is_admin()));
create policy "admin deletes dish images" on storage.objects for delete to authenticated
  using (bucket_id = 'dish-images' and (select private.is_admin()));

-- 8. Realtime. Events respect the RLS policies above, so a customer only hears about their own orders.
alter publication supabase_realtime add table orders, dishes, dish_categories, dish_dietary, dish_allergens,
  delivery_zones, blocked_dates;
