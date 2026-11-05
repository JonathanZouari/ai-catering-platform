-- Demo order for the demo customer. Run AFTER the demo users exist (see scripts/ in the PR notes).
-- Idempotent: safe to run twice.
do $$
declare
  uid uuid;
  cid uuid;
  eid uuid;
  oid uuid;
begin
  select id into uid from auth.users where email = 'demo.customer@example.com';
  if uid is null then
    raise exception 'demo.customer@example.com does not exist yet';
  end if;

  insert into public.customers (auth_user_id, full_name, email)
  values (uid, 'Demo Customer', 'demo.customer@example.com')
  on conflict (auth_user_id) do nothing;
  select id into cid from public.customers where auth_user_id = uid;

  if not exists (select 1 from public.events where customer_id = cid) then
    insert into public.events (customer_id, event_type, event_date, adults, children)
    values (cid, 'birthday', current_date + 30, 20, 5)
    returning id into eid;

    insert into public.orders (customer_id, event_id, status, total)
    values (cid, eid, 'pending_approval', 1625.00)
    returning id into oid;

    insert into public.order_items (order_id, dish_id, quantity)
    select oid, d.id, q.qty
    from (values ('Green eggs and ham', 25), ('Roast chicken', 2), ('Chocolate cake', 1)) as q (name, qty)
    join public.dishes d on d.name = q.name;
  end if;
end $$;
