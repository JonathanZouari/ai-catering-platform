-- Alcohol, sold to 18+ only (OPEN_DECISIONS #11, decided 2026-11-05).
-- A dish can be marked as alcohol; submitting an order that contains one needs the
-- customer's 18+ confirmation, recorded in orders.adult_confirmed_at.

alter table dishes add column contains_alcohol boolean not null default false;

alter table orders add column adult_confirmed_at timestamptz;
