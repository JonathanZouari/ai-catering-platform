-- Storage bucket for dish photos. dishes.image_path holds the object path
-- inside this bucket (e.g. 'dishes/<dish_id>/<file>.webp').
--
-- Public bucket: anyone can read a file by its public URL, which the menu needs.
-- No policies on storage.objects on purpose: listing, upload, replace and delete
-- are done only by the backend with the service role (which bypasses RLS).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'dish-images',
  'dish-images',
  true,
  5242880, -- 5 MB
  array['image/jpeg', 'image/png', 'image/webp', 'image/avif']
)
on conflict (id) do nothing;
