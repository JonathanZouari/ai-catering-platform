-- Storage bucket for signed price quotes (הצעות מחיר חתומות).
--
-- Private: no public URLs, and no storage.objects policies for anon / authenticated, so the
-- browser cannot read or write it through the Storage API. Uploads and downloads go through the
-- backend, which uses the service role (it bypasses RLS) and hands out short-lived signed URLs
-- after its own authorization check (ADR 0002).
--
-- Object path convention: <order_id>/<uuid>.<ext>, e.g. 3f2c…/9a1b….pdf
-- Size and type limits are enforced by Storage itself, in addition to the backend's checks.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'signed-quotes',
    'signed-quotes',
    false,
    10485760,  -- 10 MB
    array['application/pdf', 'image/jpeg', 'image/png']
)
on conflict (id) do update
    set public             = excluded.public,
        file_size_limit    = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;
