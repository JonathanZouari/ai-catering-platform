-- Customer order RPCs, called only by the backend with the server-side secret API key.
-- The migration runner owns the transaction. Apply only to the catering project.
--
-- SECURITY INVOKER: the functions run as service_role, so it needs the table and sequence privileges
-- below. They are explicit because hosted projects do not reliably give service_role table access by
-- default. Nothing here is granted to anon or authenticated; staff keep their existing table policies.
--
-- The backend validates, prices and hashes the token. These functions own the atomic write: PostgREST
-- runs each call in one transaction, so any exception leaves no customer, address, event, order, item
-- or submission behind.
grant usage on schema public to service_role;
grant select on public.dishes, public.delivery_zones to service_role;
grant select, insert on
  public.customers, public.addresses, public.events,
  public.orders, public.order_items, public.order_submissions
  to service_role;
grant usage on sequence
  public.customers_id_seq, public.addresses_id_seq, public.events_id_seq, public.orders_id_seq
  to service_role;

-- Tables have no insertion order, so catalogs and receipt lines use a natural dish order: d2 before d10.
create function public.customer_catalog() returns jsonb
language sql stable security invoker set search_path = '' as $fn$
  select jsonb_build_object(
    'dishes', coalesce((
      select jsonb_agg(jsonb_build_object(
          'id', d.id, 'metadata', d.metadata,
          'price_minor', d.price_minor, 'step_milli', d.step_milli)
        order by length(d.id), d.id)
      from public.dishes d), '[]'::jsonb),
    'zones', coalesce((
      select jsonb_agg(jsonb_build_object('city', z.city, 'fee_minor', z.fee_minor)
        order by z.fee_minor, z.city)
      from public.delivery_zones z), '[]'::jsonb));
$fn$;

-- One snapshot of a submission. Without p_order_id this is receipt recovery; with it the id must
-- belong to the same token. Returns NULL when nothing matches, so ids cannot be probed.
create function public.customer_order_read(p_token_hash text, p_order_id bigint default null)
returns jsonb
language sql stable security invoker set search_path = '' as $fn$
  select jsonb_build_object(
    'order', jsonb_build_object(
      'id', o.id, 'version', o.version, 'status', o.status, 'decision_note', o.decision_note,
      'submitted_at', to_char(o.submitted_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
      'subtotal_minor', o.subtotal_minor, 'delivery_fee_minor', o.delivery_fee_minor,
      'total_minor', o.total_minor),
    'payload', s.payload,
    'items', coalesce((
      select jsonb_agg(jsonb_build_object(
          'name', i.name, 'unit', i.unit, 'quantity_milli', i.quantity_milli,
          'unit_price_minor', i.unit_price_minor, 'line_total_minor', i.line_total_minor)
        order by length(i.dish_id), i.dish_id)
      from public.order_items i where i.order_id = o.id), '[]'::jsonb))
  from public.order_submissions s
  join public.orders o on o.id = s.order_id
  where s.token_hash = p_token_hash
    and (p_order_id is null or s.order_id = p_order_id);
$fn$;

-- Outcomes: created | existing | conflict (same token, other payload) | price_changed.
-- VOLATILE matters: at READ COMMITTED each statement after the lock wait gets a fresh snapshot, so
-- the second of two racing calls sees the first one's committed submission.
create function public.customer_order_submit(p_token_hash text, p_payload text, p_order jsonb)
returns jsonb
language plpgsql volatile security invoker set search_path = '' as $fn$
declare
  v_saved_payload text;
  v_customer_id bigint;
  v_address_id bigint;
  v_event_id bigint;
  v_order_id bigint;
  v_delivery boolean := p_order->>'fulfillment_type' = 'delivery';
begin
  perform pg_advisory_xact_lock(hashtextextended(p_token_hash, 0));

  select s.payload into v_saved_payload
  from public.order_submissions s where s.token_hash = p_token_hash;
  if found then
    if v_saved_payload <> p_payload then
      return jsonb_build_object('outcome', 'conflict');
    end if;
    return jsonb_build_object('outcome', 'existing',
                              'saved', public.customer_order_read(p_token_hash));
  end if;

  -- The backend priced from an earlier read; the quote must still hold when it is written.
  if (select count(*)
      from jsonb_to_recordset(p_order->'items') as i(dish_id text, unit_price_minor bigint)
      join public.dishes d on d.id = i.dish_id and d.price_minor = i.unit_price_minor)
       <> jsonb_array_length(p_order->'items')
     or (v_delivery and not exists (
           select 1 from public.delivery_zones z
           where z.city = p_order->>'city'
             and z.fee_minor = (p_order->>'delivery_fee_minor')::bigint)) then
    return jsonb_build_object('outcome', 'price_changed');
  end if;

  insert into public.customers(full_name, phone)
  values (p_order->>'full_name', p_order->>'phone')
  returning id into v_customer_id;

  if v_delivery then
    insert into public.addresses(customer_id, street, city)
    values (v_customer_id, p_order->>'street', p_order->>'city')
    returning id into v_address_id;
  end if;

  insert into public.events(customer_id, event_type, event_date, adults, children,
    vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)
  values (v_customer_id, p_order->>'event_type', (p_order->>'event_date')::date,
    (p_order->>'adults')::bigint, (p_order->>'children')::bigint,
    (p_order->>'vegetarian_guests')::bigint, (p_order->>'vegan_guests')::bigint,
    (p_order->>'restricted_guests')::bigint, p_order->>'dietary_notes')
  returning id into v_event_id;

  insert into public.orders(customer_id, event_id, status, fulfillment_type, requested_at,
    delivery_address_id, subtotal_minor, delivery_fee_minor, total_minor, submitted_at)
  values (v_customer_id, v_event_id, 'pending_approval', p_order->>'fulfillment_type',
    (p_order->>'requested_at')::timestamptz, v_address_id,
    (p_order->>'subtotal_minor')::bigint, (p_order->>'delivery_fee_minor')::bigint,
    (p_order->>'total_minor')::bigint, now())
  returning id into v_order_id;

  insert into public.order_items(order_id, dish_id, name, unit, quantity_milli,
    unit_price_minor, line_total_minor)
  select v_order_id, i.dish_id, i.name, i.unit, i.quantity_milli, i.unit_price_minor,
    i.line_total_minor
  from jsonb_to_recordset(p_order->'items') as i(dish_id text, name text, unit text,
    quantity_milli bigint, unit_price_minor bigint, line_total_minor bigint);

  if (select sum(i.line_total_minor) from public.order_items i where i.order_id = v_order_id)
     is distinct from (p_order->>'subtotal_minor')::bigint then
    raise exception 'order lines do not add up to the subtotal' using errcode = '23514';
  end if;

  insert into public.order_submissions(token_hash, order_id, payload)
  values (p_token_hash, v_order_id, p_payload);

  return jsonb_build_object('outcome', 'created',
                            'saved', public.customer_order_read(p_token_hash));
end; $fn$;

revoke all on function public.customer_catalog() from public, anon, authenticated;
revoke all on function public.customer_order_read(text, bigint) from public, anon, authenticated;
revoke all on function public.customer_order_submit(text, text, jsonb) from public, anon, authenticated;
grant execute on function public.customer_catalog() to service_role;
grant execute on function public.customer_order_read(text, bigint) to service_role;
grant execute on function public.customer_order_submit(text, text, jsonb) to service_role;
