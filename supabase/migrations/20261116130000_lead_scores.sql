-- Conversion score per open lead, written by backend/scripts/score_leads.py (service role).
-- A prioritisation hint for the owner only. trained_on_synthetic = true means the admin must label it a demo.

create table lead_scores (
  lead_id uuid primary key references leads (id) on delete cascade,
  probability numeric(4,3) not null check (probability between 0 and 1),
  model_version text not null check (char_length(model_version) between 1 and 50),
  trained_on_synthetic boolean not null,
  reasons jsonb not null default '[]' check (jsonb_typeof(reasons) = 'array'),
  scored_at timestamptz not null default now()
);

alter table lead_scores enable row level security;

-- Only the scoring job (service role, bypasses RLS) writes. The admin reads.
revoke all on lead_scores from anon;
revoke insert, update, delete, truncate on lead_scores from authenticated;

create policy "admin reads" on lead_scores for select to authenticated
  using ((select private.is_admin()));
