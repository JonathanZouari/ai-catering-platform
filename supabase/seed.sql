-- Sample catalog (from seed.py). Placeholder zones/fees/slots, not business rules.
insert into dish_categories (name, sort_order) values ('ראשונות', 0) on conflict (name) do nothing;
insert into dish_categories (name, sort_order) values ('סלטים', 1) on conflict (name) do nothing;
insert into dish_categories (name, sort_order) values ('עיקריות', 2) on conflict (name) do nothing;
insert into dish_categories (name, sort_order) values ('תוספות', 3) on conflict (name) do nothing;
insert into dish_categories (name, sort_order) values ('קינוחים', 4) on conflict (name) do nothing;
insert into delivery_zones (name, fee, definition) select 'תל אביב-יפו', 6000, '{"type": "city", "city": "תל אביב-יפו"}'::jsonb where not exists (select 1 from delivery_zones where name='תל אביב-יפו');
insert into delivery_zones (name, fee, definition) select 'רמת גן', 6000, '{"type": "city", "city": "רמת גן"}'::jsonb where not exists (select 1 from delivery_zones where name='רמת גן');
insert into delivery_zones (name, fee, definition) select 'גבעתיים', 6000, '{"type": "city", "city": "גבעתיים"}'::jsonb where not exists (select 1 from delivery_zones where name='גבעתיים');
insert into delivery_zones (name, fee, definition) select 'הרצליה', 9000, '{"type": "city", "city": "הרצליה"}'::jsonb where not exists (select 1 from delivery_zones where name='הרצליה');
insert into delivery_zones (name, fee, definition) select 'פתח תקווה', 10000, '{"type": "city", "city": "פתח תקווה"}'::jsonb where not exists (select 1 from delivery_zones where name='פתח תקווה');
insert into delivery_zones (name, fee, definition) select 'ראשון לציון', 11000, '{"type": "city", "city": "ראשון לציון"}'::jsonb where not exists (select 1 from delivery_zones where name='ראשון לציון');
insert into time_slots (fulfillment_type, start_time, end_time) select 'pickup', '10:00', '12:00' where not exists (select 1 from time_slots where fulfillment_type='pickup' and start_time='10:00');
insert into time_slots (fulfillment_type, start_time, end_time) select 'pickup', '12:00', '14:00' where not exists (select 1 from time_slots where fulfillment_type='pickup' and start_time='12:00');
insert into time_slots (fulfillment_type, start_time, end_time) select 'pickup', '15:00', '17:00' where not exists (select 1 from time_slots where fulfillment_type='pickup' and start_time='15:00');
insert into time_slots (fulfillment_type, start_time, end_time) select 'delivery', '09:00', '11:00' where not exists (select 1 from time_slots where fulfillment_type='delivery' and start_time='09:00');
insert into time_slots (fulfillment_type, start_time, end_time) select 'delivery', '11:00', '13:00' where not exists (select 1 from time_slots where fulfillment_type='delivery' and start_time='11:00');
insert into time_slots (fulfillment_type, start_time, end_time) select 'delivery', '14:00', '16:00' where not exists (select 1 from time_slots where fulfillment_type='delivery' and start_time='14:00');
insert into blocked_dates (date, reason) values ('2026-11-10', 'סגור להזמנות') on conflict do nothing;
insert into blocked_dates (date, reason) values ('2026-11-16', 'סגור להזמנות') on conflict do nothing;
insert into allergens (id, name) values (1, 'גלוטן') on conflict do nothing;
insert into allergens (id, name) values (2, 'אגוזים') on conflict do nothing;
insert into allergens (id, name) values (3, 'בוטנים') on conflict do nothing;
insert into allergens (id, name) values (4, 'שומשום') on conflict do nothing;
insert into allergens (id, name) values (5, 'ביצים') on conflict do nothing;
insert into allergens (id, name) values (6, 'חלב') on conflict do nothing;
insert into allergens (id, name) values (7, 'דגים') on conflict do nothing;
insert into allergens (id, name) values (8, 'סויה') on conflict do nothing;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'חומוס ביתי', 'חומוס עם טחינה ושמן זית', 'per_tray', 12000, 'מגש 2 ק״ג' from dish_categories where name='ראשונות' and not exists (select 1 from dishes where name='חומוס ביתי') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='שומשום'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'קובה סלק', 'קובה סלק במילוי בשר', 'per_item', 1800, 'יחידה' from dish_categories where name='ראשונות' and not exists (select 1 from dishes where name='קובה סלק') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'meat', false, false from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='גלוטן'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'סלט ירקות קצוץ', 'עגבנייה, מלפפון ובצל', 'per_tray', 9000, 'מגש 3 ק״ג' from dish_categories where name='סלטים' and not exists (select 1 from dishes where name='סלט ירקות קצוץ') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'סלט קינואה', 'קינואה, ירקות ואגוזי מלך', 'per_tray', 14000, 'מגש 2 ק״ג' from dish_categories where name='סלטים' and not exists (select 1 from dishes where name='סלט קינואה') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='אגוזים'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'חזה עוף בתנור', 'עוף צלוי בתיבול עשבים', 'per_weight', 6500, 'ק״ג' from dish_categories where name='עיקריות' and not exists (select 1 from dishes where name='חזה עוף בתנור') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'meat', false, false from d returning dish_id) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'סלמון בגריל', 'פילה סלמון ברוטב לימון', 'per_guest', 4500, 'למנה' from dish_categories where name='עיקריות' and not exists (select 1 from dishes where name='סלמון בגריל') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', false, false from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='דגים'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'לזניה גבינות', 'לזניה עם ממרח עגבניות', 'per_tray', 26000, 'מגש 12 מנות' from dish_categories where name='עיקריות' and not exists (select 1 from dishes where name='לזניה גבינות') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'dairy', true, false from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='גלוטן'), 'contains' from d returning 1), a1 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='חלב'), 'contains' from d returning 1), a2 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='ביצים'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'אורז בסמטי', 'אורז עם שקדים קלויים', 'per_tray', 8000, 'מגש 3 ק״ג' from dish_categories where name='תוספות' and not exists (select 1 from dishes where name='אורז בסמטי') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='אגוזים'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'תפוחי אדמה בתנור', 'תפוחי אדמה עם רוזמרין', 'per_tray', 7500, 'מגש 3 ק״ג' from dish_categories where name='תוספות' and not exists (select 1 from dishes where name='תפוחי אדמה בתנור') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'עוגת שוקולד', 'עוגת שוקולד מריר', 'per_item', 5500, 'עוגה' from dish_categories where name='קינוחים' and not exists (select 1 from dishes where name='עוגת שוקולד') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'dairy', true, false from d returning dish_id), a0 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='גלוטן'), 'contains' from d returning 1), a1 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='ביצים'), 'contains' from d returning 1), a2 as (insert into dish_allergens (dish_id, allergen_id, status) select d.id, (select id from allergens where name='חלב'), 'contains' from d returning 1) select 1;
with d as (insert into dishes (category_id, name, description, pricing_unit, unit_price, unit_label) select id, 'סלט פירות', 'פירות העונה', 'per_guest', 1500, 'למנה' from dish_categories where name='קינוחים' and not exists (select 1 from dishes where name='סלט פירות') returning id), dd as (insert into dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) select id, 'pareve', true, true from d returning dish_id) select 1;

-- Demo customers, events and orders (fictitious).
insert into customers (full_name, email, phone)
select * from (values
  ('דנה כהן','dana.demo@example.com','050-0000001'),
  ('יוסי לוי','yossi.demo@example.com','050-0000002'),
  ('מיכל אברהם','michal.demo@example.com','050-0000003')
) v(n,e,p) where not exists (select 1 from customers where email = v.e);

with c as (select id, email from customers where email like '%.demo@example.com'),
ev as (
  insert into events (customer_id, event_type, event_date, adults, children, vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)
  select c.id, v.t, current_date + v.d, v.a, v.k, v.vg, v.vn, v.r, v.note
  from c join (values
    ('dana.demo@example.com','יום הולדת',14,20,8,3,1,0,null),
    ('yossi.demo@example.com','ארוחת שבת',7,12,4,2,0,1,'אלרגיה לאגוזים'),
    ('michal.demo@example.com','בר מצווה',30,60,25,8,3,2,null)
  ) v(em,t,d,a,k,vg,vn,r,note) on v.em = c.email
  where not exists (select 1 from events e where e.customer_id = c.id)
  returning id, customer_id
)
insert into orders (customer_id, event_id, status, fulfillment_type, requested_at, delivery_address, delivery_zone_id, subtotal, delivery_fee, total, submitted_at)
select ev.customer_id, ev.id,
  case c.email when 'dana.demo@example.com' then 'draft' when 'yossi.demo@example.com' then 'pending_approval' else 'approved' end,
  case c.email when 'yossi.demo@example.com' then 'pickup' else 'delivery' end,
  now() + interval '7 days',
  case c.email when 'yossi.demo@example.com' then null else 'רחוב הדמו 1, תל אביב' end,
  case c.email when 'yossi.demo@example.com' then null else (select id from delivery_zones where name = 'תל אביב-יפו') end,
  null, null, null, null
from ev join c on c.id = ev.customer_id;

insert into order_items (order_id, dish_id, quantity)
select o.id, d.id, q.qty
from orders o join customers c on c.id = o.customer_id and c.email like '%.demo@example.com'
cross join (values ('חומוס ביתי',2),('סלמון בגריל',20),('עוגת שוקולד',1)) q(dn,qty)
join dishes d on d.name = q.dn
on conflict do nothing;
