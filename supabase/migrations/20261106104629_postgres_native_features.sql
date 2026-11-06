-- Remove the last SQLite-driven compromises now that the database is Supabase Postgres only.

-- 1. JSON columns: json -> jsonb (validated, indexable, supports containment queries).
alter table ai_messages         alter column content type jsonb using content::jsonb;
alter table ai_change_proposals alter column changes type jsonb using changes::jsonb;

-- 2. Keep updated_at correct on every write, including writes made straight from the
--    browser through the Data API (e.g. staff changing a dish image or price).
create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'settings','staff_users','categories','delivery_zones','customers','dishes','orders']
  loop
    execute format(
      'create trigger set_updated_at before update on public.%I
         for each row execute function private.set_updated_at()', t);
  end loop;
end $$;
