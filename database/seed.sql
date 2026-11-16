-- SYNTHETIC DATA ONLY: invented people, dishes, prices and zones for development.
-- Not real business data. Run after migrations/20261105000000_initial_schema.sql.
-- Dietary/allergen facts are left unknown (NULL / no row) unless stated; unknown != free.
-- Deterministic: random() is seeded so a fresh database always gets the same data.

select setseed(0.42);

insert into dish_categories (name, sort_order) values
    ('Starters', 1), ('Salads', 2), ('Main courses', 3),
    ('Side dishes', 4), ('Desserts', 5), ('Drinks', 6);

insert into allergens (id, name) values
    (1, 'Gluten'), (2, 'Tree nuts'), (3, 'Peanuts'), (4, 'Milk'), (5, 'Eggs'),
    (6, 'Sesame'), (7, 'Soy'), (8, 'Fish'), (9, 'Shellfish'), (10, 'Mustard');

insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label, min_quantity)
select c.id, v.name, v.descr, v.unit::pricing_unit, v.price, v.label, v.minq
from (values
    ('Starters',     'Hummus platter',         'Classic hummus with olive oil',  'per_tray',   90, 'tray (10 servings)', 1),
    ('Starters',     'Mini focaccia',          'Herb focaccia squares',          'per_item',    4, 'piece', 20),
    ('Starters',     'Stuffed vine leaves',    'Rice-stuffed vine leaves',       'per_item',    3, 'piece', 20),
    ('Salads',       'Greek salad',            'Tomato, cucumber, olives, feta', 'per_guest',  12, null, null),
    ('Salads',       'Quinoa salad',           'Quinoa, herbs, lemon dressing',  'per_guest',  14, null, null),
    ('Salads',       'Tabbouleh',              'Parsley and bulgur salad',       'per_tray',   80, 'tray (10 servings)', 1),
    ('Main courses', 'Roasted chicken',        'Herb-roasted chicken pieces',    'per_guest',  38, null, null),
    ('Main courses', 'Baked salmon',           'Salmon fillet with lemon',       'per_guest',  52, null, null),
    ('Main courses', 'Slow-cooked brisket',    'Brisket in red wine sauce',      'per_weight',120, 'kg', 3),
    ('Main courses', 'Vegetable lasagna',      'Layered vegetables and cheese',  'per_tray',  220, 'tray (12 servings)', 1),
    ('Side dishes',  'Herbed rice',            'Basmati rice with herbs',        'per_guest',   8, null, null),
    ('Side dishes',  'Roasted potatoes',       'Rosemary roasted potatoes',      'per_weight', 35, 'kg', 2),
    ('Desserts',     'Brownie squares',        'Chocolate brownie',              'per_item',    6, 'piece', 20),
    ('Desserts',     'Seasonal fruit platter', 'Assorted cut fruit',             'per_tray',  150, 'tray (15 servings)', 1),
    ('Drinks',       'Mint lemonade',          'Fresh lemonade with mint',       'per_item',   18, 'liter', 5)
) as v(cat, name, descr, unit, price, label, minq)
join dish_categories c on c.name = v.cat;

-- Only some dishes have verified dietary info; the rest get no row (= not provided).
insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan, verified_at)
select d.id, v.k::kashrut_class, v.veg, v.vegan, timestamptz '2026-11-01 00:00:00+00'
from (values
    ('Hummus platter',      'pareve', true,  true),
    ('Greek salad',         'dairy',  true,  false),
    ('Roasted chicken',     'meat',   false, false),
    ('Slow-cooked brisket', 'meat',   false, false),
    ('Vegetable lasagna',   'dairy',  true,  false),
    ('Mint lemonade',       'pareve', true,  true)
) as v(name, k, veg, vegan)
join dishes d on d.name = v.name;

-- Hummus: contains sesame, free of gluten/peanuts/milk. Lasagna: contains gluten and milk.
-- Brownie gluten is explicitly unknown. Everything else stays unknown (no row).
insert into dish_allergens (dish_id, allergen_id, status)
select d.id, v.aid, v.st::allergen_status
from (values
    ('Hummus platter',    6, 'contains'), ('Hummus platter', 1, 'free'),
    ('Hummus platter',    3, 'free'),     ('Hummus platter', 4, 'free'),
    ('Vegetable lasagna', 1, 'contains'), ('Vegetable lasagna', 4, 'contains'),
    ('Brownie squares',   1, 'unknown')
) as v(name, aid, st)
join dishes d on d.name = v.name;

insert into delivery_zones (name, fee, definition) values
    ('City center',   40, '{"type":"city_list","cities":["Tel Aviv"]}'),
    ('Nearby area',   70, '{"type":"city_list","cities":["Ramat Gan","Givatayim","Holon"]}'),
    ('Extended area',120, '{"type":"radius_km","max":40}');

insert into time_slots (fulfillment_type, weekday, start_time, end_time, capacity) values
    ('pickup',   0, '10:00', '14:00', null),
    ('pickup',   4, '10:00', '14:00', null),
    ('delivery', 0, '11:00', '17:00', 10),
    ('delivery', 4, '11:00', '17:00', 10);

insert into blocked_dates (date, reason) values ('2026-12-25', 'Sample closed day');

insert into customers (full_name, email, phone)
select n, lower(replace(n, ' ', '.')) || '@example.com', '050-000' || lpad((row_number() over ())::text, 4, '0')
from unnest(array[
    'Dana Sample', 'Ron Sample', 'Maya Example', 'Eitan Demo', 'Noa Test', 'Yossi Placeholder',
    'Tamar Fake', 'Omer Mock', 'Lior Synthetic', 'Shira Dummy', 'Avi Sample', 'Gali Example'
]) as n;

-- One event + order per customer, cycling through every order status, with items,
-- price snapshots (non-draft), AI conversations and a pending proposal on drafts.
do $$
declare
    c          record;
    d          record;
    z          record;
    n          int := 0;
    ev_id      uuid;
    o_id       uuid;
    conv_id    uuid;
    st         order_status;
    ft         fulfillment_type;
    ev_date    date;
    adults     int;
    children   int;
    guests     int;
    qty        numeric;
    line       numeric;
    sub        numeric;
    fee        numeric;
    zone_id    uuid;
    city       text;
    types      text[] := array['Birthday', 'Office lunch', 'Family gathering', 'Wedding', 'Bar mitzvah', 'Corporate event'];
begin
    for c in select * from customers order by email loop
        n := n + 1;
        st := (array['draft', 'pending_approval', 'approved', 'rejected'])[(n % 4) + 1]::order_status;
        ft := case when n % 2 = 0 then 'delivery' else 'pickup' end::fulfillment_type;
        ev_date := date '2026-12-01' + (n * 2) + (n % 3);
        if ev_date = date '2026-12-25' then ev_date := ev_date + 1; end if;
        adults   := 10 + (random() * 40)::int;
        children := (random() * 8)::int;
        guests   := adults + children;

        insert into events (customer_id, event_type, event_date, adults, children,
                            vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)
        values (c.id, types[(n % 6) + 1], ev_date, adults, children,
                least(adults, (random() * 6)::int), least(adults, (random() * 3)::int),
                (random() * 2)::int,
                case when n % 5 = 0 then 'One guest with a nut allergy (owner to review)' end)
        returning id into ev_id;

        select * into z from delivery_zones order by random() limit 1;
        zone_id := case when ft = 'delivery' then z.id end;
        city := (array['Tel Aviv', 'Ramat Gan', 'Holon'])[(n % 3) + 1];

        insert into orders (customer_id, event_id, status, version, fulfillment_type, requested_at,
                            delivery_address, delivery_zone_id)
        values (c.id, ev_id, st, case when st = 'draft' then 1 else 2 end, ft,
                (ev_date + time '12:00') at time zone 'UTC',
                case when ft = 'delivery' then 'Sample St ' || n || ', ' || city end,
                zone_id)
        returning id into o_id;

        sub := 0;
        for d in select * from dishes order by random() limit 4 loop
            qty := case d.pricing_unit
                when 'per_guest'  then guests
                when 'per_tray'   then ceil(guests / 10.0)
                when 'per_weight' then greatest(coalesce(d.min_quantity, 1), round(guests * 0.25))
                else                   greatest(coalesce(d.min_quantity, 1), guests * 2)
            end;
            line := qty * d.unit_price;
            sub := sub + line;
            if st = 'draft' then
                insert into order_items (order_id, dish_id, quantity) values (o_id, d.id, qty);
            else
                insert into order_items (order_id, dish_id, quantity, snapshot_name,
                                         snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total)
                values (o_id, d.id, qty, d.name, d.pricing_unit, d.unit_price, line);
            end if;
        end loop;

        fee := case when ft = 'delivery' then z.fee else 0 end;
        if st <> 'draft' then
            update orders set subtotal = sub, delivery_fee = fee, total = sub + fee,
                   submitted_at = timestamptz '2026-11-02 09:00:00+00' + (n || ' hours')::interval,
                   decided_at = case when st in ('approved', 'rejected')
                                     then timestamptz '2026-11-03 10:00:00+00' + (n || ' hours')::interval end,
                   decision_note = case st when 'approved' then 'Sample approval'
                                           when 'rejected' then 'Sample rejection: date unavailable' end
            where id = o_id;
        else
            insert into ai_conversations (order_id) values (o_id) returning id into conv_id;
            insert into ai_messages (conversation_id, role, content) values
                (conv_id, 'user',      '{"text":"Can you add a dessert for the guests?"}'),
                (conv_id, 'assistant', '{"text":"I can propose adding brownie squares. Review the change below."}');
            insert into ai_change_proposals (order_id, conversation_id, base_order_version, changes,
                                             price_before, price_after)
            values (o_id, conv_id, 1,
                    jsonb_build_array(jsonb_build_object('op', 'add_item', 'dish', 'Brownie squares', 'quantity', 20)),
                    sub, sub + 120);
        end if;
    end loop;
end $$;
