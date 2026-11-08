-- Catalog access for the browser: public read, owner-only writes, Realtime, and dish images.
--
-- Supersedes the "no browser access" stance of 20261105100000_catalog.sql for the catalog only:
-- the customer menu subscribes to Realtime with the publishable key, and Realtime delivers a
-- change only to clients whose RLS SELECT policy allows the row.
--
-- Who is the owner: app_metadata.role = 'owner' in the user's JWT. app_metadata can only be set
-- with the secret key (never user_metadata, which the user can edit). Claims refresh with the
-- token, so a role change takes effect at the next token refresh.

-- ---------------------------------------------------------------- owner check
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to anon, authenticated;

create function private.is_owner() returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
    select coalesce((auth.jwt() -> 'app_metadata' ->> 'role') = 'owner', false);
$$;

revoke execute on function private.is_owner() from public;
grant execute on function private.is_owner() to anon, authenticated;

-- ---------------------------------------------------------------- grants
grant select on public.dish_categories, public.dishes, public.dish_dietary,
                public.allergens, public.dish_allergens
    to anon, authenticated;
grant insert, update, delete on public.dish_categories, public.dishes, public.dish_dietary,
                                public.allergens, public.dish_allergens
    to authenticated;

-- ---------------------------------------------------------------- read policies
-- One SELECT policy per table (public condition OR owner) instead of two permissive policies.
create policy "catalog_categories_read" on public.dish_categories
    for select to anon, authenticated
    using (is_active or (select private.is_owner()));

-- A dish is public while it is available and its category is active.
create policy "catalog_dishes_read" on public.dishes
    for select to anon, authenticated
    using (
        (is_available and exists (
            select 1 from public.dish_categories c
            where c.id = category_id and c.is_active
        ))
        or (select private.is_owner())
    );

-- Dietary rows and allergen statuses follow their dish (the subquery is itself filtered by RLS).
create policy "catalog_dietary_read" on public.dish_dietary
    for select to anon, authenticated
    using (exists (select 1 from public.dishes d where d.id = dish_id));

create policy "catalog_dish_allergens_read" on public.dish_allergens
    for select to anon, authenticated
    using (exists (select 1 from public.dishes d where d.id = dish_id));

create policy "catalog_allergens_read" on public.allergens
    for select to anon, authenticated
    using (true);

-- ---------------------------------------------------------------- owner write policies
-- UPDATE needs both USING and WITH CHECK; INSERT needs WITH CHECK; DELETE needs USING.
do $$
declare
    t text;
begin
    foreach t in array array['dish_categories', 'dishes', 'dish_dietary', 'allergens', 'dish_allergens']
    loop
        execute format(
            'create policy %I on public.%I for insert to authenticated
                 with check ((select private.is_owner()))', 'catalog_' || t || '_owner_insert', t);
        execute format(
            'create policy %I on public.%I for update to authenticated
                 using ((select private.is_owner())) with check ((select private.is_owner()))',
            'catalog_' || t || '_owner_update', t);
        execute format(
            'create policy %I on public.%I for delete to authenticated
                 using ((select private.is_owner()))', 'catalog_' || t || '_owner_delete', t);
    end loop;
end;
$$;

-- Indexes for the policy subqueries.
create index if not exists ix_dishes_available on public.dishes (is_available);

-- ---------------------------------------------------------------- realtime
-- The customer menu refetches the catalog when any of these change.
alter publication supabase_realtime
    add table public.dish_categories, public.dishes, public.dish_dietary, public.dish_allergens;

-- ---------------------------------------------------------------- dish images
-- Public bucket: menu photos are public content, served from the CDN URL.
-- No storage.objects write policies: uploads go only through the backend
-- (POST /api/admin/dishes/{id}/image), which checks the owner role and the file.
-- Path convention: <dish_id>/<uuid>.<ext>; dishes.image_path stores that path.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880,  -- 5 MB
        array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
    set public             = excluded.public,
        file_size_limit    = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
