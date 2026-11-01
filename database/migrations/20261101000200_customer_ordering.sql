-- Customer ordering: quantity recommendations and scheduling (Phase 5).

create type category_type as enum ('salad', 'main', 'side', 'dessert', 'drink', 'other');

alter table dish_categories
    add column category_type category_type not null default 'other';

-- How many portions one tray, item, or weight unit gives. Null = no recommendation.
alter table dishes
    add column servings_per_unit numeric(10, 2) check (servings_per_unit > 0);

-- A null caterer_id is a platform default; a caterer row overrides it.
create table quantity_rules (
    id uuid primary key default gen_random_uuid(),
    caterer_id uuid references caterers (id) on delete cascade,
    category_type category_type not null,
    portions_per_adult numeric(5, 2) not null check (portions_per_adult >= 0),
    portions_per_child numeric(5, 2) not null check (portions_per_child >= 0)
);
create unique index quantity_rules_platform_idx
    on quantity_rules (category_type) where caterer_id is null;
create unique index quantity_rules_caterer_idx
    on quantity_rules (caterer_id, category_type) where caterer_id is not null;
alter table quantity_rules enable row level security;

-- Draft values, unverified until a real caterer reviews them (OPEN_DECISIONS #3).
insert into quantity_rules (category_type, portions_per_adult, portions_per_child) values
    ('salad', 1.50, 1.00),
    ('main', 1.00, 0.60),
    ('side', 1.00, 0.60),
    ('dessert', 1.00, 1.00),
    ('drink', 1.00, 1.00),
    ('other', 0.00, 0.00);

alter table time_slots add constraint time_slots_caterer_id_id_key unique (caterer_id, id);

alter table orders
    add column time_slot_id uuid,
    add column delivery_city text,
    add constraint orders_time_slot_fkey
        foreign key (caterer_id, time_slot_id) references time_slots (caterer_id, id);
create index orders_time_slot_idx on orders (caterer_id, time_slot_id);
