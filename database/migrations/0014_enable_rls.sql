-- Supabase's Data API (PostgREST) serves the public schema to anyone holding the public anon
-- key. The app never uses it: the backend connects as the table owner, which RLS doesn't
-- apply to (not forced). RLS with no policies shuts anon/authenticated out of every table.
-- Every later migration that creates a table must enable RLS on it too.
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
