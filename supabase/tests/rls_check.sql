-- Lists every table in the public schema with its RLS state and policies.
-- Every row must have ok = true (RLS on and at least one policy).
--
-- RLS is not in the CREATE TABLE migration; it is turned on in
-- migrations/20261105111743_auth_rls_storage_realtime.sql (and for events in
-- 20261108091000_events_table.sql). This reads the live catalog instead of the SQL.
--
-- Run (read-only):  supabase db query --remote --read-only -f supabase/tests/rls_check.sql

select c.relname as table_name,
       c.relrowsecurity and count(p.polname) > 0 as ok,
       c.relrowsecurity as rls_on,
       count(p.polname) as policies,
       string_agg(p.polname, ' | ' order by p.polname) as policy_names
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
left join pg_policy p on p.polrelid = c.oid
where n.nspname = 'public' and c.relkind in ('r', 'p')
group by c.relname, c.relrowsecurity
order by ok, c.relname;
