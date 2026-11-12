-- Realtime signal for the customer menu.
--
-- Why not subscribe to the catalog tables directly: Realtime checks the SELECT policy against the
-- new row, so hiding a dish (is_available = false) or a category would never reach anonymous
-- clients, and the hidden dish would stay on their open menu. Instead every catalog write bumps
-- one public row; clients refetch the catalog from the backend when it changes.

create table public.catalog_changes (
    id          smallint primary key default 1 constraint ck_catalog_changes_single_row check (id = 1),
    changed_at  timestamptz not null default now()
);

insert into public.catalog_changes (id) values (1);

alter table public.catalog_changes enable row level security;
grant select on public.catalog_changes to anon, authenticated;
create policy "catalog_changes_read" on public.catalog_changes
    for select to anon, authenticated
    using (true);

-- SECURITY DEFINER so the owner's writes can bump the row without being granted UPDATE on it.
-- It lives in the unexposed private schema, takes no input and is only callable as a trigger.
create function private.touch_catalog() returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    update public.catalog_changes set changed_at = now() where id = 1;
    return null;
end;
$$;

revoke execute on function private.touch_catalog() from public, anon, authenticated;

-- Statement level: one bump per write, however many rows it touched.
create trigger trg_catalog_changed after insert or update or delete on public.dish_categories
    for each statement execute function private.touch_catalog();
create trigger trg_catalog_changed after insert or update or delete on public.dishes
    for each statement execute function private.touch_catalog();
create trigger trg_catalog_changed after insert or update or delete on public.dish_dietary
    for each statement execute function private.touch_catalog();
create trigger trg_catalog_changed after insert or update or delete on public.allergens
    for each statement execute function private.touch_catalog();
create trigger trg_catalog_changed after insert or update or delete on public.dish_allergens
    for each statement execute function private.touch_catalog();

alter publication supabase_realtime
    drop table public.dish_categories, public.dishes, public.dish_dietary, public.dish_allergens;
alter publication supabase_realtime add table public.catalog_changes;
