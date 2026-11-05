-- Public-read bucket for dish images; only an admin (app_metadata.role = 'admin') may write.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('dish-images', 'dish-images', true, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;

create policy "dish images public read" on storage.objects for select
  using (bucket_id = 'dish-images');
create policy "dish images admin write" on storage.objects for all to authenticated
  using (bucket_id = 'dish-images' and (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin')
  with check (bucket_id = 'dish-images' and (auth.jwt() -> 'app_metadata' ->> 'role') = 'admin');
