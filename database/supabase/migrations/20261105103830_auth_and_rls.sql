-- Auth + row level security.
--
-- Roles:
--   admin    = auth user whose app_metadata.role = 'admin' (set only server-side
--              with the service role; app_metadata is not user-editable).
--   customer = any other signed-in user, linked through customers.auth_user_id.
--
-- Access through the Data API (role `authenticated`):
--   customer -> SELECT only, and only rows of their own orders.
--   admin    -> full read/write on all order data.
-- `anon` gets nothing. The backend's privileged connection bypasses RLS, so all
-- business writes (pricing, status changes) still go through backend services.

-- ---------------------------------------------------------------- new user -> customer row
create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer -- runs as owner: the auth service role cannot write public.customers
set search_path = ''
as $$
begin
  insert into public.customers (auth_user_id, full_name, email, phone)
  values (
    new.id,
    coalesce(nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''), new.email),
    new.email,
    nullif(trim(new.raw_user_meta_data ->> 'phone'), '')
  );
  return new;
end;
$$;
-- Trigger-only; nobody should call it through the API.
revoke execute on function private.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- ---------------------------------------------------------------- grants (RLS decides rows)
revoke all on all tables in schema public from anon;
-- Server-side only (backend / admin scripts); bypasses RLS.
grant all on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

grant select on public.customers, public.events, public.orders, public.order_items,
  public.ai_conversations, public.ai_messages, public.ai_change_proposals
  to authenticated;
grant insert, update, delete on public.customers, public.events, public.orders,
  public.order_items, public.ai_conversations, public.ai_messages, public.ai_change_proposals
  to authenticated; -- only admin policies allow writes

-- admin check: ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
-- (auth.* wrapped in SELECT so Postgres evaluates it once per query, not per row)

-- ---------------------------------------------------------------- read: own rows, or everything for admin
create policy customers_select on public.customers
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or (select auth.uid()) = auth_user_id
  );

create policy events_select on public.events
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or customer_id in (
      select c.id from public.customers c where c.auth_user_id = (select auth.uid())
    )
  );

create policy orders_select on public.orders
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or customer_id in (
      select c.id from public.customers c where c.auth_user_id = (select auth.uid())
    )
  );

create policy order_items_select on public.order_items
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or order_id in (
      select o.id from public.orders o
      join public.customers c on c.id = o.customer_id
      where c.auth_user_id = (select auth.uid())
    )
  );

create policy ai_conversations_select on public.ai_conversations
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or order_id in (
      select o.id from public.orders o
      join public.customers c on c.id = o.customer_id
      where c.auth_user_id = (select auth.uid())
    )
  );

create policy ai_messages_select on public.ai_messages
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or conversation_id in (
      select ac.id from public.ai_conversations ac
      join public.orders o on o.id = ac.order_id
      join public.customers c on c.id = o.customer_id
      where c.auth_user_id = (select auth.uid())
    )
  );

create policy ai_change_proposals_select on public.ai_change_proposals
  for select to authenticated
  using (
    ((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'
    or order_id in (
      select o.id from public.orders o
      join public.customers c on c.id = o.customer_id
      where c.auth_user_id = (select auth.uid())
    )
  );

-- ---------------------------------------------------------------- write: admin only
do $$
declare
  t text;
  admin text := $a$((select auth.jwt()) -> 'app_metadata' ->> 'role') = 'admin'$a$;
begin
  foreach t in array array['customers', 'events', 'orders', 'order_items',
                           'ai_conversations', 'ai_messages', 'ai_change_proposals']
  loop
    execute format('create policy %1$I on public.%2$I for insert to authenticated with check (%3$s)',
                   t || '_admin_insert', t, admin);
    execute format('create policy %1$I on public.%2$I for update to authenticated using (%3$s) with check (%3$s)',
                   t || '_admin_update', t, admin);
    execute format('create policy %1$I on public.%2$I for delete to authenticated using (%3$s)',
                   t || '_admin_delete', t, admin);
  end loop;
end;
$$;
