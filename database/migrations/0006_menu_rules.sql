-- Menu selection rules (OPEN_DECISIONS #3, #4, #5, decided 2026-11-02).

-- How many adult portions one unit of a dish serves; null = no quantity recommendation.
alter table dishes
  add column serves_adults numeric(10, 2) check (serves_adults > 0);

-- Vegetarian and vegan are separate groups within adults + children.
alter table events
  add constraint events_veg_vegan_total check (
    vegetarian_guests + vegan_guests <= adults + children
  );

-- Owner-editable business settings, a single row.
create table business_settings (
  id smallint primary key default 1,
  child_portion numeric(3, 2) not null default 0.75, -- a child's share of an adult portion
  lead_days int not null default 3, -- earliest event date = today (Israel time) + lead_days
  constraint business_settings_single_row check (id = 1),
  constraint business_settings_child check (child_portion > 0 and child_portion <= 1),
  constraint business_settings_lead_days check (lead_days between 0 and 60)
);
insert into business_settings (id) values (1);

alter table business_settings enable row level security;
