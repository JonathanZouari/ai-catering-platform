-- Leads: people who asked about catering an event, before any order exists.
-- A lead is "won" when it ended in an approved order and "lost" when it did not.

CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'quoted', 'won', 'lost');
CREATE TYPE lead_source AS ENUM ('referral', 'google', 'instagram', 'website');

CREATE TABLE leads (
  id               uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name        text          NOT NULL,
  phone            text,
  email            text,
  -- Same labels as events.event_type (the customer event form).
  event_type       text          NOT NULL,
  event_date       date          NOT NULL,
  guests           integer       NOT NULL CHECK (guests > 0),
  budget_per_guest numeric(10,2) NOT NULL CHECK (budget_per_guest >= 0),
  source           lead_source   NOT NULL,
  is_returning     boolean       NOT NULL DEFAULT false,
  status           lead_status   NOT NULL DEFAULT 'new',
  created_at       timestamptz   NOT NULL DEFAULT now(),
  updated_at       timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX leads_status_idx ON leads (status);

-- Same reason as in 0001: no public Data API access.
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
