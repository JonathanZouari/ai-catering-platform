-- Customer login by email magic link (OPEN_DECISIONS #1, decided: magic link).
-- Every new Supabase Auth user gets a customers row linked through auth_user_id.
-- The business owner is marked with app_metadata.role = 'owner' (set only with the service role,
-- never from user_metadata, which users can edit).

alter table customers
  add constraint customers_auth_user_id_fkey
  foreign key (auth_user_id) references auth.users(id) on delete set null;

-- Private schema: not exposed through the Data API, so this function is not a public endpoint.
create schema if not exists private;

create or replace function private.handle_new_auth_user()
returns trigger
language plpgsql
security definer  -- runs from the auth trigger, which has no rights on public.customers
set search_path = ''
as $$
begin
  insert into public.customers (auth_user_id, full_name, email)
  values (
    new.id,
    coalesce(nullif(new.raw_user_meta_data ->> 'full_name', ''), split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (auth_user_id) do nothing;
  return new;
end;
$$;

revoke all on function private.handle_new_auth_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_auth_user();
