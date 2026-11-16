-- Leads: "call me back" requests from the website, no account needed.
-- Visitors only write through public.submit_lead(); only the admin reads leads and changes status and notes.

create type lead_status as enum ('new', 'contacted', 'quoted', 'won', 'lost');

create table leads (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (char_length(full_name) between 2 and 100),
  phone text not null check (phone ~ '^0[0-9]{8,9}$'), -- stored normalized: digits only, local format
  email text check (email is null or (char_length(email) <= 200 and email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$')),
  event_type text check (char_length(event_type) <= 60),
  event_date date,
  guests int check (guests between 1 and 5000),
  message text check (char_length(message) <= 1000),
  status lead_status not null default 'new',
  notes text check (char_length(notes) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index leads_created_at_idx on leads (created_at desc);
create index leads_phone_created_at_idx on leads (phone, created_at);

create trigger leads_updated_at before update on leads
  for each row execute function set_updated_at();

-- Supabase grants every new table to anon and authenticated by default; narrow it.
alter table leads enable row level security;
revoke all on leads from anon;
revoke insert, update, delete, truncate on leads from authenticated;
grant update (status, notes) on leads to authenticated;

create policy "admin reads" on leads for select to authenticated
  using ((select private.is_admin()));
create policy "admin updates" on leads for update to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));

-- New functions in private must not be callable by everyone unless granted explicitly.
alter default privileges in schema private revoke execute on functions from public;

create function private.submit_lead(payload jsonb) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_phone text := regexp_replace(coalesce(payload ->> 'phone', ''), '\D', '', 'g');
  v_name text := nullif(trim(payload ->> 'name'), '');
begin
  -- Honeypot: a hidden field people never fill. Bots get a normal-looking success.
  if coalesce(payload ->> 'company', '') <> '' then
    return;
  end if;

  if v_phone like '972%' then
    v_phone := '0' || substr(v_phone, 4);
  end if;
  if v_name is null or char_length(v_name) < 2 then
    raise exception 'נא למלא שם מלא' using errcode = '22023';
  end if;
  if v_phone !~ '^0[0-9]{8,9}$' then
    raise exception 'מספר הטלפון אינו תקין' using errcode = '22023';
  end if;

  -- Flood guards: one request per phone per day, and a global hourly cap.
  if exists (select 1 from public.leads where phone = v_phone and created_at > now() - interval '24 hours') then
    raise exception 'כבר קיבלנו פנייה מהמספר הזה. נחזור אליך בהקדם.' using errcode = '23505';
  end if;
  if (select count(*) from public.leads where created_at > now() - interval '1 hour') >= 60 then
    raise exception 'יש עומס פניות כרגע. נסו שוב בעוד כמה דקות.' using errcode = '54000';
  end if;

  insert into public.leads (full_name, phone, email, event_type, event_date, guests, message)
  values (
    v_name,
    v_phone,
    nullif(lower(trim(payload ->> 'email')), ''),
    nullif(trim(payload ->> 'event_type'), ''),
    nullif(payload ->> 'event_date', '')::date,
    nullif(payload ->> 'guests', '')::int,
    nullif(trim(payload ->> 'message'), '')
  );
exception
  when check_violation or invalid_text_representation or invalid_datetime_format or datetime_field_overflow then
    raise exception 'חלק מהפרטים אינם תקינים' using errcode = '22023';
end $$;

-- anon needs schema usage to reach the function; every other private function stays revoked from it.
grant usage on schema private to anon;
revoke execute on function private.submit_lead(jsonb) from public;
grant execute on function private.submit_lead(jsonb) to anon, authenticated;

-- Thin invoker wrapper, same pattern as submit_order.
create function public.submit_lead(payload jsonb) returns void
language sql set search_path = '' as $$ select private.submit_lead(payload) $$;
revoke execute on function public.submit_lead(jsonb) from public;
grant execute on function public.submit_lead(jsonb) to anon, authenticated;

-- Realtime: new leads appear on the owner dashboard. Events respect RLS, so only the admin hears them.
alter publication supabase_realtime add table leads;
