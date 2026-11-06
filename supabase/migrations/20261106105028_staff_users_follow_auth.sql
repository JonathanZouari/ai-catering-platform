-- staff_users holds only business data about a staff member (name, active flag).
-- Everything about logging in belongs to Supabase Auth (auth.users):
--   * staff_users.id is already a FK to auth.users(id) ON DELETE CASCADE (initial schema).
--   * last_login_at duplicated auth.users.last_sign_in_at and nothing updated it: dropped.
--   * email is kept as a read-only copy for staff lists (the auth schema is not exposed
--     to the browser), but Auth is now its only source: it is filled from auth.users on
--     insert and follows every email change made in Auth.

alter table staff_users drop column last_login_at;

-- Fill / overwrite the email from auth.users whenever a staff row is written.
-- security definer: the caller (a staff member in the admin) cannot read auth.users.
create or replace function private.staff_email_from_auth()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  select lower(u.email) into new.email from auth.users u where u.id = new.id;
  if new.email is null then
    raise exception 'staff_users.id % has no Supabase Auth user with an email', new.id;
  end if;
  return new;
end;
$$;

create trigger staff_email_from_auth
  before insert or update of id, email on public.staff_users
  for each row execute function private.staff_email_from_auth();

-- Keep the copy in step when the email changes in Supabase Auth.
create or replace function private.sync_staff_email()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.staff_users set email = lower(new.email) where id = new.id;
  return new;
end;
$$;

create trigger sync_staff_email
  after update of email on auth.users
  for each row
  when (old.email is distinct from new.email)
  execute function private.sync_staff_email();

revoke all on function private.staff_email_from_auth(), private.sync_staff_email()
  from public, anon, authenticated;
