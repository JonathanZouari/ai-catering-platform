-- Behavioural SQL test. Needs a real database with both migrations applied; all fixtures roll back.
-- Execute as the project SQL administrator, with one of:
--   node supabase/tests/local-postgres.mjs                 (PGlite with Auth/Storage stubs)
--   python supabase/tests/live_local_checks.py <local-url> (psql -v ON_ERROR_STOP=1, plus lock races)
-- Single connection only, so it cannot show lock races. Not pgTAP: `supabase test db` will not report it.
--
-- PASS is raised by the last DO block. Any earlier error aborts the transaction, so that block cannot
-- run, even without ON_ERROR_STOP. Do not add statements after the final ROLLBACK.
begin;
set local plpgsql.check_asserts = on;

create function pg_temp.expect_error(stmt text, want_state text, want_message text default '')
returns void language plpgsql as $fn$
declare got_state text; got_message text;
begin
    begin
        execute stmt;
    exception when others then
        get stacked diagnostics got_state = returned_sqlstate, got_message = message_text;
        if got_state <> want_state or position(want_message in got_message) = 0 then
            raise exception 'Wrong error for [%]: % "%" (wanted % "%")',
                stmt, got_state, got_message, want_state, want_message;
        end if;
        return;
    end;
    raise exception 'Statement was accepted: %', stmt;
end $fn$;

create function pg_temp.affected(stmt text) returns bigint language plpgsql as $fn$
declare n bigint;
begin
    execute stmt;
    get diagnostics n = row_count;
    return n;
end $fn$;

create function pg_temp.ctx(name text) returns bigint language sql as
$fn$ select current_setting('test.' || name)::bigint $fn$;

create function pg_temp.new_order(customer bigint, address bigint, fulfillment text, order_status text)
returns bigint language plpgsql as $fn$
declare new_event bigint; new_id bigint;
begin
    insert into public.events(customer_id,event_type,event_date,adults)
      values(customer,'Test',current_date+20,10) returning id into new_event;
    insert into public.orders(customer_id,event_id,status,fulfillment_type,requested_at,delivery_address_id,
        subtotal_minor,delivery_fee_minor,total_minor,submitted_at)
      values(customer,new_event,order_status,fulfillment,now()+interval '20 days',
        case when fulfillment='delivery' then address end,8500,
        case when fulfillment='delivery' then 6000 else 0 end,
        case when fulfillment='delivery' then 14500 else 8500 end,now())
      returning id into new_id;
    return new_id;
end $fn$;

-- ---- Catalog: RLS, policies, views, functions and every anonymous grant ----
do $test$
declare r record; priv text; probe_ok boolean;
begin
    assert (select count(*) from pg_class c join pg_namespace s on s.oid=c.relnamespace
            where s.nspname='public' and c.relkind='r') = 16, 'Expected exactly 16 public tables';
    assert not exists (select 1 from pg_class c join pg_namespace s on s.oid=c.relnamespace
            where s.nspname='public' and c.relkind='r' and not c.relrowsecurity), 'Public table without RLS';

    -- Any narrower policy must fail here first: see "Hidden rows" in the migration header.
    assert (select count(*) from pg_policies where schemaname='public') = 16, 'Expected 16 public policies';
    assert not exists (select 1 from pg_policies where schemaname='public' and not (
            policyname='catering_managers' and cmd='ALL' and roles='{authenticated}'
            and qual like '%app_metadata%' and with_check like '%app_metadata%'
            and qual like '%catering_owner%' and qual like '%catering_manager%'
            and qual not like '%user_metadata%' and with_check not like '%user_metadata%')),
        'Unexpected public policy';

    assert (select count(*) from pg_class c join pg_namespace s on s.oid=c.relnamespace
            where s.nspname='public' and c.relkind='v' and c.reloptions @> array['security_invoker=true']) = 5,
        'Expected 5 security_invoker views';
    assert not exists (select 1 from pg_class c join pg_namespace s on s.oid=c.relnamespace
            where s.nspname='public' and c.relkind='v'
            and not coalesce(c.reloptions @> array['security_invoker=true'], false)), 'View without security_invoker';

    for r in select p.oid, p.proname, p.prosecdef, p.proconfig, p.prorettype from pg_proc p
             join pg_namespace s on s.oid=p.pronamespace where s.nspname='public'
             -- Hosted automatic-RLS setup owns this DDL event trigger; it is not an application RPC.
             and not (p.proname='rls_auto_enable' and p.prorettype='event_trigger'::regtype
                      and exists (select 1 from pg_event_trigger e where e.evtfoid=p.oid))
             and not exists (select 1 from pg_depend d where d.objid=p.oid and d.deptype='e') loop
        assert not r.prosecdef, 'SECURITY DEFINER function: ' || r.proname;
        assert r.proconfig @> array['search_path=""'], 'Function without empty search_path: ' || r.proname;
        assert not has_function_privilege('anon', r.oid, 'execute'), 'Anonymous execute: ' || r.proname;
        assert not has_function_privilege('authenticated', r.oid, 'execute'), 'Authenticated execute: ' || r.proname;
    end loop;

    assert not has_schema_privilege('anon','public','create'), 'Anonymous CREATE on public';
    assert not has_schema_privilege('authenticated','public','create'), 'Authenticated CREATE on public';

    for r in select c.oid, c.relname, c.relkind from pg_class c join pg_namespace s on s.oid=c.relnamespace
             where s.nspname='public' and c.relkind in ('r','v','m','f','p') loop
        foreach priv in array array['select','insert','update','delete','truncate','references','trigger'] loop
            assert not has_table_privilege('anon', r.oid, priv), format('Anonymous %s on %s', priv, r.relname);
        end loop;
        assert not has_any_column_privilege('anon', r.oid, 'select,insert,update,references'),
            'Anonymous column grant on ' || r.relname;
        foreach priv in array array['truncate','references','trigger'] loop
            assert not has_table_privilege('authenticated', r.oid, priv),
                format('Authenticated %s on %s', priv, r.relname);
        end loop;
        if r.relkind = 'v' then
            assert has_table_privilege('authenticated', r.oid, 'select'), 'Staff cannot read view ' || r.relname;
            foreach priv in array array['insert','update','delete'] loop
                assert not has_table_privilege('authenticated', r.oid, priv),
                    format('Authenticated %s on view %s', priv, r.relname);
            end loop;
        end if;
    end loop;
    for r in select c.oid, c.relname from pg_class c join pg_namespace s on s.oid=c.relnamespace
             where s.nspname='public' and c.relkind='S' loop
        assert not has_sequence_privilege('anon', r.oid, 'usage,select,update'), 'Anonymous sequence ' || r.relname;
    end loop;

    create table public.default_privilege_probe(id bigint);
    probe_ok := not has_table_privilege('anon','public.default_privilege_probe','select')
            and not has_table_privilege('authenticated','public.default_privilege_probe','select');
    drop table public.default_privilege_probe;
    assert probe_ok, 'New public tables are not closed by default';

    assert (select format_type(atttypid, atttypmod) from pg_attribute
            where attrelid='public.order_submissions'::regclass and attname='payload') = 'text', 'Payload must be text';
    assert not exists (select 1 from pg_attribute a join pg_class c on c.oid=a.attrelid
            join pg_namespace s on s.oid=c.relnamespace
            where s.nspname='public' and c.relkind='v' and a.attnum>0 and a.atttypid='numeric'::regtype),
        'A view column is numeric, not bigint';
end; $test$;

-- ---- Invariants as administrator ----
do $test$
declare
    today date := (now() at time zone 'Asia/Jerusalem')::date;
    v_customer bigint; v_address bigint; v_address2 bigint; v_order bigint; v_pickup bigint; v_other bigint;
    v_delivery bigint; v_collection bigint; v_receipt bigint; v_refund bigint; v_item bigint;
    v_ingredient bigint; v_batch bigint; v_empty_batch bigint; v_empty_ingredient bigint; s record;
    v_payload text := '{"b":1,  "a":"שלום"}';
begin
    insert into public.customers(full_name,phone) values ('TEST ONLY','0500000000') returning id into v_customer;
    insert into public.addresses(customer_id,street,city) values(v_customer,'Test 1','Test') returning id into v_address;
    insert into public.addresses(customer_id,street,city) values(v_customer,'Test 2','Test') returning id into v_address2;
    v_order := pg_temp.new_order(v_customer,v_address,'delivery','pending_approval');
    v_pickup := pg_temp.new_order(v_customer,v_address,'pickup','pending_approval');
    v_other := pg_temp.new_order(v_customer,v_address,'delivery','draft');
    insert into public.order_items values(v_order,'d1','Test dish','tray',1000,8500,8500);
    assert (select total_minor from public.orders where id=v_order)=14500, 'Order total';

    -- Canonical payload text survives byte for byte; invalid JSON is rejected.
    insert into public.order_submissions values(repeat('a',64),v_order,v_payload);
    assert (select payload from public.order_submissions where order_id=v_order)=v_payload, 'Payload was normalized';
    perform pg_temp.expect_error(format($$insert into public.order_submissions values(%L,%s,'{not json')$$,
        repeat('b',64),v_pickup),'22P02');

    -- Order status transitions.
    perform pg_temp.expect_error(format($$update public.orders set status='approved',decided_at=now() where id=%s$$,v_other),
        '23514','invalid order status transition');
    update public.orders set status='pending_approval' where id=v_other;
    perform pg_temp.expect_error(format($$update public.orders set status='draft' where id=%s$$,v_other),
        '23514','invalid order status transition');
    update public.orders set status='rejected',decided_at=now() where id=v_other;
    perform pg_temp.expect_error(format($$update public.orders set status='approved' where id=%s$$,v_other),
        '23514','invalid order status transition');

    -- Food drop-off on both sides, and snapshot/address guards.
    perform pg_temp.expect_error(format($$insert into public.deliveries(order_id,address_id,window_start,window_end)
        values(%s,%s,now(),now()+interval '1 hour')$$,v_pickup,v_address),'23514','food drop-off requires a delivery order');
    insert into public.deliveries(order_id,address_id,purpose,window_start,window_end)
      values(v_pickup,v_address,'equipment_collection',now(),now()+interval '1 hour') returning id into v_collection;
    perform pg_temp.expect_error(format($$update public.deliveries set purpose='food_drop_off' where id=%s$$,v_collection),
        '23514','food drop-off requires a delivery order');
    insert into public.deliveries(order_id,address_id,window_start,window_end,address_snapshot)
      values(v_order,v_address,now()+interval '20 days',now()+interval '20 days 2 hours','{"street":"forged"}')
      returning id into v_delivery;
    assert (select address_snapshot->>'street' from public.deliveries where id=v_delivery)='Test 1', 'Snapshot was forged';
    perform pg_temp.expect_error(format($$update public.orders set fulfillment_type='pickup',delivery_address_id=null,
        delivery_fee_minor=0,total_minor=8500 where id=%s$$,v_order),'23514','food drop-off requires a delivery order');
    update public.addresses set street='Changed' where id=v_address;
    assert (select address_snapshot->>'street' from public.deliveries where id=v_delivery)='Test 1', 'Snapshot changed';
    perform pg_temp.expect_error(format($$update public.deliveries set address_snapshot='{}' where id=%s$$,v_delivery),
        '23514','snapshots are immutable');
    perform pg_temp.expect_error(format($$update public.deliveries set address_id=%s where id=%s$$,v_address2,v_delivery),
        '23514','create a new delivery');

    -- Payments, refunds and summary arithmetic.
    insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at)
      values('receipt',v_order,'ILS',14500,'cash',now()) returning id into v_receipt;
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at)
        values('receipt',%s,'USD',1,'cash',now())$$,v_order),'23503');
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',14501,'cash',now(),%s,'test')$$,v_order,v_receipt),'23514','refunds exceed the original receipt');
    insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
      values('refund',v_order,'ILS',4500,'cash',now(),v_receipt,'partial') returning id into v_refund;
    select * into s from public.order_payment_summary where order_id=v_order;
    assert (s.total_minor,s.received_minor,s.refunded_minor,s.net_paid_minor,s.balance_due_minor)
        = (14500::bigint,14500::bigint,4500::bigint,10000::bigint,4500::bigint), 'Payment summary with partial refund';
    assert pg_typeof(s.net_paid_minor)='bigint'::regtype, 'Summary must be bigint';
    select * into s from public.order_payment_summary where order_id=v_pickup;
    assert (s.net_paid_minor,s.balance_due_minor) = (0::bigint,8500::bigint), 'Summary without payments';
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',10001,'cash',now(),%s,'test')$$,v_order,v_receipt),'23514','refunds exceed the original receipt');
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',1,'cash',now(),%s,'test')$$,v_order,v_refund),'23514','a refund must reference a receipt');
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',1,'cash',now(),%s,'test')$$,v_pickup,v_receipt),'23503');
    insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
      values('refund',v_order,'ILS',10000,'cash',now(),v_receipt,'exact remainder');

    -- Equipment stock and dispatch limits.
    insert into public.equipment_items(name,category) values('TEST TABLE','table') returning id into v_item;
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity) values(v_item,'purchase',3);
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'dispatch',4,%s)$$,v_item,v_order),'23514','not enough equipment on hand');
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id) values(v_item,'dispatch',2,v_order);
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'return',3,%s)$$,v_item,v_order),'23514','more equipment returned or lost');
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id,notes)
        values(%s,'lost_at_event',3,%s,'test')$$,v_item,v_order),'23514','more equipment returned or lost');
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'return',1,%s)$$,v_item,v_pickup),'23514','more equipment returned or lost');
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id,notes) values(v_item,'lost_at_event',1,v_order,'test');
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id) values(v_item,'return',1,v_order);
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'return',1,%s)$$,v_item,v_order),'23514','more equipment returned or lost');
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,notes)
        values(%s,'write_off',3,'test')$$,v_item),'23514','not enough equipment on hand');
    select * into s from public.equipment_stock where equipment_item_id=v_item;
    assert (s.on_hand,s.out_at_events) = (2::bigint,0::bigint), 'Equipment stock arithmetic';
    assert (select quantity_out from public.equipment_out_by_order where equipment_item_id=v_item and order_id=v_order)=0,
        'Equipment out by order';

    -- Ingredient stock, expiry, not-before-receipt and history guards.
    insert into public.ingredients(name,base_unit) values('TEST INGREDIENT','g') returning id into v_ingredient;
    insert into public.ingredient_batches(ingredient_id,lot_code,received_on,expires_on)
      values(v_ingredient,'EXPIRED',today-3,today-1) returning id into v_batch;
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
        values(%s,'receipt',100,now()-interval '10 days')$$,v_batch),'23514','dated before the batch was received');
    insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
      values(v_batch,'receipt',100,now()-interval '2 days');
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity)
        values(%s,'consumption',1)$$,v_batch),'23514','cannot consume an expired batch');
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity,notes)
        values(%s,'waste',101,'test')$$,v_batch),'23514','not enough of this batch on hand');
    perform pg_temp.expect_error(format($$update public.ingredients set base_unit='ml' where id=%s$$,v_ingredient),
        '23514','cannot change the unit of recorded stock');
    perform pg_temp.expect_error(format($$update public.ingredient_batches set received_on=%L where id=%s$$,today-4,v_batch),
        '23514','cannot rewrite recorded batch');
    perform pg_temp.expect_error(format($$update public.ingredient_batches set expires_on=%L where id=%s$$,today+4,v_batch),
        '23514','cannot rewrite recorded batch');
    insert into public.ingredient_batches(ingredient_id,lot_code,received_on)
      values(v_ingredient,'FRESH',today) returning id into v_empty_batch;
    update public.ingredient_batches set received_on=today-1 where id=v_empty_batch;
    insert into public.ingredient_movements(batch_id,movement_type,quantity) values(v_empty_batch,'receipt',40);
    insert into public.ingredient_movements(batch_id,movement_type,quantity) values(v_empty_batch,'consumption',15);
    assert (select on_hand from public.ingredient_batch_stock where batch_id=v_batch)=100, 'Batch stock';
    select * into s from public.ingredient_stock where ingredient_id=v_ingredient;
    assert (s.usable_on_hand,s.expired_on_hand) = (25::bigint,100::bigint), 'Usable and expired stock';
    insert into public.ingredients(name,base_unit) values('TEST UNUSED','g') returning id into v_empty_ingredient;
    update public.ingredients set base_unit='ml' where id=v_empty_ingredient;

    -- Asia/Jerusalem business date: 22:30 UTC on 14 March 2026 is already 15 March (UTC+2).
    insert into public.ingredient_batches(ingredient_id,lot_code,received_on,expires_on)
      values(v_ingredient,'TZ-RECEIVED','2026-03-15','2026-03-20') returning id into v_empty_batch;
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
        values(%s,'receipt',10,'2026-03-14 21:30:00+00')$$,v_empty_batch),'23514','dated before the batch was received');
    insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
      values(v_empty_batch,'receipt',10,'2026-03-14 22:30:00+00');
    insert into public.ingredient_batches(ingredient_id,lot_code,received_on,expires_on)
      values(v_ingredient,'TZ-EXPIRES','2026-03-01','2026-03-14') returning id into v_empty_batch;
    insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
      values(v_empty_batch,'receipt',10,'2026-03-02 12:00:00+00');
    insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
      values(v_empty_batch,'consumption',1,'2026-03-14 21:30:00+00');
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity,occurred_at)
        values(%s,'consumption',1,'2026-03-14 22:30:00+00')$$,v_empty_batch),'23514','cannot consume an expired batch');

    -- Case-insensitive uniqueness.
    insert into public.customers(full_name,email) values('TEST','case-test@example.test');
    perform pg_temp.expect_error($$insert into public.customers(full_name,email) values('TEST','CASE-Test@Example.Test')$$,
        '23505','customers_email_lower_idx');
    insert into public.employees(full_name,role,email) values('TEST','chef','case-test@example.test');
    perform pg_temp.expect_error($$insert into public.employees(full_name,role,email) values('TEST','chef','CASE-Test@Example.Test')$$,
        '23505','employees_email_lower_idx');
    perform pg_temp.expect_error($$insert into public.ingredients(name,base_unit) values('test ingredient','g')$$,
        '23505','ingredients_name_lower_idx');
    perform pg_temp.expect_error($$insert into public.equipment_items(name,category) values('test table','table')$$,
        '23505','equipment_items_name_lower_idx');

    -- Append-only ledgers, for this privileged role and for service_role where it exists.
    perform pg_temp.expect_error(format('update public.%I set created_at=now()',t),'23514','append-only')
      from unnest(array['payments','equipment_movements','ingredient_movements']) t;
    perform pg_temp.expect_error(format('delete from public.%I',t),'23514','append-only')
      from unnest(array['payments','equipment_movements','ingredient_movements']) t;
    perform pg_temp.expect_error(format('truncate public.%I',t),'23514','append-only')
      from unnest(array['payments','equipment_movements','ingredient_movements']) t;
    perform pg_temp.expect_error('truncate public.orders cascade','23514','append-only');
    if exists (select 1 from pg_roles where rolname='service_role')
       and has_table_privilege('service_role','public.payments','truncate') then
        set local role service_role;
        perform pg_temp.expect_error('truncate public.payments','23514','append-only');
        reset role;
    end if;

    perform set_config('test.customer',v_customer::text,true);
    perform set_config('test.address',v_address::text,true);
    perform set_config('test.order',v_order::text,true);
    perform set_config('test.receipt',v_receipt::text,true);
    perform set_config('test.item',v_item::text,true);
    perform set_config('test.ingredient',v_ingredient::text,true);
    perform set_config('test.batch',v_batch::text,true);
end; $test$;

-- ---- Anonymous: denied everywhere, even with a forged staff claim ----
set local role anon;
set local "request.jwt.claims" to '{"role":"anon","app_metadata":{"role":"catering_owner"}}';
do $test$
declare r record;
begin
    for r in select c.relname, c.relkind, (select a.attname from pg_attribute a
                 where a.attrelid=c.oid and a.attnum=1) as first_column
             from pg_class c join pg_namespace s on s.oid=c.relnamespace
             where s.nspname='public' and c.relkind in ('r','v') loop
        perform pg_temp.expect_error(format('select 1 from public.%I',r.relname),'42501','permission denied');
        if r.relkind='r' then
            -- Aggregate views reject writes during rewrite (55000), before permission checks.
            -- Their missing write privileges are verified in the catalog block above.
            perform pg_temp.expect_error(format('insert into public.%I default values',r.relname),'42501','permission denied');
            perform pg_temp.expect_error(format('update public.%I set %I=%I',r.relname,r.first_column,r.first_column),'42501','permission denied');
            perform pg_temp.expect_error(format('delete from public.%I',r.relname),'42501','permission denied');
            perform pg_temp.expect_error(format('truncate public.%I',r.relname),'42501','permission denied');
        end if;
    end loop;
    perform pg_temp.expect_error($$select nextval('public.customers_id_seq')$$,'42501','permission denied');
end; $test$;
reset role;

-- ---- Signed-in users without a staff role see and change nothing ----
set local role authenticated;
do $test$
declare claims text; r record; n bigint;
begin
    foreach claims in array array[
        '',
        '{}',
        '{"role":"authenticated","app_metadata":{}}',
        '{"role":"authenticated","app_metadata":{},"user_metadata":{"role":"catering_owner"}}',
        '{"role":"catering_owner"}',
        '{"role":"authenticated","app_metadata":{"role":"driver"}}',
        '{"role":"authenticated","app_metadata":{"role":"authenticated"}}',
        '{"role":"authenticated","app_metadata":{"role":"CATERING_OWNER"}}',
        '{"role":"authenticated","app_metadata":{"role":["catering_owner"]}}'
    ] loop
        perform set_config('request.jwt.claims',claims,true);
        for r in select c.relname from pg_class c join pg_namespace s on s.oid=c.relnamespace
                 where s.nspname='public' and c.relkind in ('r','v') loop
            execute format('select count(*) from public.%I',r.relname) into n;
            assert n=0, format('Claims %s can read %s', claims, r.relname);
        end loop;
        for r in select c.relname from pg_class c join pg_namespace s on s.oid=c.relnamespace
                 where s.nspname='public' and c.relkind='r' loop
            assert pg_temp.affected(format('delete from public.%I',r.relname))=0,
                format('Claims %s can delete from %s', claims, r.relname);
        end loop;
        assert pg_temp.affected($$update public.customers set full_name='HACK'$$)=0, 'Wrong role updated customers';
        assert pg_temp.affected($$update public.dishes set price_minor=0$$)=0, 'Wrong role updated dishes';
        assert pg_temp.affected($$update public.orders set decision_note='HACK'$$)=0, 'Wrong role updated orders';
        perform pg_temp.expect_error($$insert into public.customers(full_name,phone) values('HACK','1')$$,'42501','row-level security');
        perform pg_temp.expect_error($$insert into public.dishes values('hack','{}',1,1)$$,'42501','row-level security');
        perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at)
            values('receipt',%s,'ILS',1,'cash',now())$$,pg_temp.ctx('order')),'42501','row-level security');
    end loop;
end; $test$;
reset role;

-- ---- Manager write path as authenticated: all row locks must work under RLS ----
set local role authenticated;
set local "request.jwt.claims" to '{"role":"authenticated","app_metadata":{"role":"catering_manager"}}';
do $test$
declare
    today date := (now() at time zone 'Asia/Jerusalem')::date;
    v_customer bigint; v_address bigint; v_order bigint; v_receipt bigint; v_item bigint;
    v_ingredient bigint; v_batch bigint; t text;
begin
    assert exists(select 1 from public.customers where id=pg_temp.ctx('customer')), 'Manager cannot read test customer';
    insert into public.customers(full_name,phone) values('MANAGER TEST','0500000001') returning id into v_customer;
    update public.customers set phone='0500000002' where id=v_customer;
    insert into public.addresses(customer_id,street,city) values(v_customer,'Manager 1','Test') returning id into v_address;
    v_order := pg_temp.new_order(v_customer,v_address,'delivery','draft');
    update public.orders set status='pending_approval' where id=v_order;
    update public.orders set status='approved',decided_at=now() where id=v_order;
    insert into public.order_items values(v_order,'d1','Dish','tray',1000,8500,8500);
    insert into public.order_submissions values(repeat('c',64),v_order,'{"manager":true}');
    insert into public.deliveries(order_id,address_id,window_start,window_end)
      values(v_order,v_address,now(),now()+interval '1 hour');

    insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at)
      values('receipt',v_order,'ILS',14500,'cash',now()) returning id into v_receipt;
    insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
      values('refund',v_order,'ILS',500,'cash',now(),v_receipt,'manager');
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',14001,'cash',now(),%s,'too much')$$,v_order,v_receipt),'23514','refunds exceed the original receipt');
    assert (select balance_due_minor from public.order_payment_summary where order_id=v_order)=500, 'Manager summary';

    insert into public.equipment_items(name,category) values('MANAGER TABLE','table') returning id into v_item;
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity) values(v_item,'purchase',5);
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id) values(v_item,'dispatch',2,v_order);
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id) values(v_item,'return',1,v_order);
    assert (select on_hand from public.equipment_stock where equipment_item_id=v_item)=4, 'Manager equipment stock';

    insert into public.ingredients(name,base_unit) values('MANAGER INGREDIENT','g') returning id into v_ingredient;
    insert into public.ingredient_batches(ingredient_id,received_on,expires_on) values(v_ingredient,today,today+5) returning id into v_batch;
    insert into public.ingredient_movements(batch_id,movement_type,quantity) values(v_batch,'receipt',50);
    insert into public.ingredient_movements(batch_id,movement_type,quantity,order_id) values(v_batch,'consumption',20,v_order);
    assert (select usable_on_hand from public.ingredient_stock where ingredient_id=v_ingredient)=30, 'Manager ingredient stock';

    update public.dishes set price_minor=price_minor where id='d1';
    insert into public.delivery_zones values('MANAGER ZONE',1);
    assert pg_temp.affected($$delete from public.delivery_zones where city='MANAGER ZONE'$$)=1, 'Manager delete';

    foreach t in array array['payments','equipment_movements','ingredient_movements'] loop
        perform pg_temp.expect_error(format('update public.%I set created_at=now()',t),'23514','append-only');
        perform pg_temp.expect_error(format('delete from public.%I',t),'23514','append-only');
    end loop;
    for t in select c.relname from pg_class c join pg_namespace s on s.oid=c.relnamespace
             where s.nspname='public' and c.relkind='r' loop
        perform pg_temp.expect_error(format('truncate public.%I',t),'42501','permission denied');
    end loop;
end; $test$;
set local "request.jwt.claims" to '{"role":"authenticated","app_metadata":{"role":"catering_owner"}}';
do $test$
declare v_customer bigint;
begin
    assert (select count(*) from public.dishes)>0, 'Owner cannot read dishes';
    insert into public.customers(full_name,phone) values('OWNER TEST','0500000003') returning id into v_customer;
    assert pg_temp.affected(format('delete from public.customers where id=%s',v_customer))=1, 'Owner delete';
end; $test$;
reset role;

-- ---- Fail closed: an insert-only role whose RLS hides the parent row must be rejected ----
create policy test_hidden_parent on public.payments for insert to authenticated
  with check ((select auth.jwt()->'app_metadata'->>'role')='test_hidden');
create policy test_hidden_parent on public.equipment_movements for insert to authenticated
  with check ((select auth.jwt()->'app_metadata'->>'role')='test_hidden');
create policy test_hidden_parent on public.ingredient_movements for insert to authenticated
  with check ((select auth.jwt()->'app_metadata'->>'role')='test_hidden');
create policy test_hidden_parent on public.deliveries for insert to authenticated
  with check ((select auth.jwt()->'app_metadata'->>'role')='test_hidden');
set local role authenticated;
set local "request.jwt.claims" to '{"role":"authenticated","app_metadata":{"role":"test_hidden"}}';
do $test$
begin
    -- Control: the policy admits this role, so the rejections below come from the trigger checks.
    insert into public.equipment_movements(equipment_item_id,movement_type,quantity)
      values(pg_temp.ctx('item'),'purchase',1);
    perform pg_temp.expect_error(format($$insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,refund_of_payment_id,reason)
        values('refund',%s,'ILS',1,'cash',now(),%s,'hidden')$$,pg_temp.ctx('order'),pg_temp.ctx('receipt')),
        '23514','a refund must reference a receipt');
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'dispatch',1,%s)$$,pg_temp.ctx('item'),pg_temp.ctx('order')),'23514','not enough equipment on hand');
    perform pg_temp.expect_error(format($$insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)
        values(%s,'return',1,%s)$$,pg_temp.ctx('item'),pg_temp.ctx('order')),'23514','equipment item is not visible');
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity)
        values(%s,'consumption',1)$$,pg_temp.ctx('batch')),'23514','ingredient batch is not visible');
    perform pg_temp.expect_error(format($$insert into public.ingredient_movements(batch_id,movement_type,quantity,notes)
        values(%s,'waste',1,'hidden')$$,pg_temp.ctx('batch')),'23514','ingredient batch is not visible');
    perform pg_temp.expect_error(format($$insert into public.deliveries(order_id,address_id,window_start,window_end)
        values(%s,%s,now(),now()+interval '1 hour')$$,pg_temp.ctx('order'),pg_temp.ctx('address')),
        '23514','food drop-off requires a delivery order');
end; $test$;
reset role;

do $test$
begin
    raise notice 'PASS (SQL behaviour, one connection): catalog, anonymous, wrong roles, manager writes, invariants, fail-closed. Lock races and hosted services are not covered.';
end; $test$;
rollback;
