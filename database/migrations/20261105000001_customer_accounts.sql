-- Customer accounts (OPEN #1) and more storage. Guest checkout stays: auth_user_id is nullable.
-- auth_user_id deliberately has no FK to auth.users: local and test Postgres have no auth schema.
ALTER TABLE customers
  ADD COLUMN auth_user_id uuid UNIQUE,
  ADD COLUMN avatar_path text CHECK (length(avatar_path) <= 300);

ALTER TABLE dish_categories ADD COLUMN image_path text CHECK (length(image_path) <= 300);

-- Private files attached to an order (bucket order-files); the backend serves signed URLs.
CREATE TABLE order_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id uuid NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  path text NOT NULL CHECK (length(path) <= 300),
  original_name text NOT NULL CHECK (length(original_name) <= 100),
  content_type text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')),
  size_bytes int NOT NULL CHECK (size_bytes > 0),
  uploaded_by text NOT NULL CHECK (uploaded_by IN ('customer', 'admin')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX order_files_order_id_idx ON order_files (order_id);
ALTER TABLE order_files ENABLE ROW LEVEL SECURITY;
