-- Synthetic demo data for the catering platform. Every person, phone and address is made up.
-- Money in agorot, quantities in thousandths of a unit (see docs/DATABASE_SCHEMA.md).
--
-- The two demo logins (demo.staff@example.com, demo.customer@example.com) are created in
-- Supabase Auth separately; this file links them by email if they exist.

begin;

-- Settings ---------------------------------------------------------------------
insert into settings (id, default_max_guests_per_day, min_lead_days, vat_rate_bp, currency)
values (1, 200, 3, 1800, 'ILS');

-- Staff (linked to the demo staff login) --------------------------------------
insert into staff_users (id, email, full_name)
select id, lower(email), 'צוות דמו'
from auth.users where lower(email) = 'demo.staff@example.com';

-- Menu -------------------------------------------------------------------------
insert into categories (name, sort_order) values
  ('סלטים', 1), ('מנות פתיחה וקנאפה', 2), ('דגים', 3), ('עיקריות', 4),
  ('תוספות', 5), ('לחמים', 6), ('קינוחים', 7), ('שתייה', 8);

insert into allergens (name, sort_order) values
  ('גלוטן', 1), ('חלב', 2), ('ביצים', 3), ('דגים', 4), ('אגוזים', 5),
  ('בוטנים', 6), ('שומשום', 7), ('סויה', 8), ('סלרי', 9), ('חרדל', 10);

-- name, category, unit, unit_label, price, per adult, per child, step, min, kashrut, veg, vegan, image, available
insert into dishes (name, category_id, unit, unit_label, price_agorot, qty_per_adult_milli,
                    qty_per_child_milli, qty_step_milli, qty_min_milli, kashrut, is_vegetarian,
                    is_vegan, image_path, is_available, sort_order, description)
select v.name, c.id, v.unit::dish_unit, v.unit_label, v.price, v.adult, v.child, v.step, v.min_qty,
       v.kashrut::kashrut, v.veg, v.vegan, v.image, v.available, v.sort, v.descr
from (values
  ('סלט ירוק גדול', 'סלטים', 'tray', 'מגש ל-10 סועדים', 14500, 100, 50, 1000, 1000, 'pareve', true, true, 'categories/food-salad.webp', true, 1, 'עלים, מלפפון, עשבי תיבול ורוטב לימון'),
  ('סלט קינואה וירקות קלויים', 'סלטים', 'tray', 'מגש ל-10 סועדים', 16500, 100, 50, 1000, 1000, 'pareve', true, true, 'categories/food-salad.webp', true, 2, null),
  ('טבולה', 'סלטים', 'tray', 'מגש ל-10 סועדים', 13500, 100, 50, 1000, 1000, 'pareve', true, true, 'categories/food-salad.webp', true, 3, 'בורגול, פטרוזיליה, נענע ולימון'),
  ('סלט יווני עם פטה', 'סלטים', 'tray', 'מגש ל-10 סועדים', 17500, 100, 50, 1000, 1000, 'dairy', true, false, 'categories/food-salad.webp', true, 4, null),
  ('סלט עונתי של השף', 'סלטים', 'tray', 'מגש ל-10 סועדים', 15500, null, null, 1000, 1000, null, null, null, 'categories/food-salad.webp', true, 5, 'משתנה לפי העונה. פרטי כשרות ואלרגנים בבירור'),
  ('מיני פריקסה', 'מנות פתיחה וקנאפה', 'item', 'יחידה', 900, 2000, 1000, 1000, 10000, 'pareve', false, false, 'categories/food-canapes.webp', true, 1, 'טונה, ביצה, תפוח אדמה וחריף'),
  ('קנאפה סלמון מעושן', 'מנות פתיחה וקנאפה', 'item', 'יחידה', 1100, 2000, 0, 1000, 10000, 'dairy', false, false, 'categories/food-canapes.webp', true, 2, null),
  ('פטריות ממולאות', 'מנות פתיחה וקנאפה', 'item', 'יחידה', 750, 2000, 1000, 1000, 10000, 'pareve', true, true, 'categories/food-canapes.webp', true, 3, null),
  ('בורקס גבינה', 'מנות פתיחה וקנאפה', 'item', 'יחידה', 650, 1500, 1000, 1000, 10000, 'dairy', true, false, 'categories/food-canapes.webp', true, 4, null),
  ('סלמון בתנור', 'דגים', '100g', 'ל-100 גרם', 2475, 1500, 800, 5000, 10000, 'pareve', false, false, 'categories/food-fish.webp', true, 1, 'בעשבי תיבול ולימון'),
  ('דג לברק בעשבי תיבול', 'דגים', '100g', 'ל-100 גרם', 2200, 1500, 800, 5000, 10000, 'pareve', false, false, 'categories/food-fish.webp', true, 2, null),
  ('קציצות בקר ברוטב עגבניות', 'עיקריות', 'tray', 'מגש ל-8 סועדים', 21000, 125, 60, 1000, 1000, 'meat', false, false, 'categories/food-main.webp', true, 1, null),
  ('עוף בגריל בסילאן', 'עיקריות', '100g', 'ל-100 גרם', 1650, 2000, 1000, 5000, 10000, 'meat', false, false, 'categories/food-main.webp', true, 2, null),
  ('לזניה ירקות', 'עיקריות', 'tray', 'מגש ל-8 סועדים', 19500, 125, 125, 1000, 1000, 'dairy', true, false, 'categories/food-main.webp', true, 3, null),
  ('שניצלונים', 'עיקריות', '100g', 'ל-100 גרם', 1400, 1500, 1500, 5000, 10000, 'meat', false, false, 'categories/food-main.webp', true, 4, null),
  ('מגש אנטיפסטי אישי', 'עיקריות', 'guest', 'לסועד', 4500, 1000, 0, 1000, 10000, 'pareve', true, true, 'categories/food-main.webp', true, 5, null),
  ('אורז פרסי', 'תוספות', '100g', 'ל-100 גרם', 600, 1500, 1000, 5000, 10000, 'pareve', true, true, 'categories/food-sides.webp', true, 1, null),
  ('תפוחי אדמה בתנור', 'תוספות', 'tray', 'מגש ל-10 סועדים', 9500, 100, 100, 1000, 1000, 'pareve', true, true, 'categories/food-sides.webp', true, 2, null),
  ('ירקות קלויים', 'תוספות', 'tray', 'מגש ל-10 סועדים', 11000, 100, 50, 1000, 1000, 'pareve', true, true, 'categories/food-sides.webp', true, 3, null),
  ('חלה מתוקה', 'לחמים', 'item', 'חלה ל-8 סועדים', 2800, 125, 125, 1000, 1000, 'pareve', true, false, 'categories/food-bread.webp', true, 1, null),
  ('לחמניות שאור', 'לחמים', 'item', 'יחידה', 350, 1000, 1000, 1000, 10000, 'pareve', true, true, 'categories/food-bread.webp', true, 2, null),
  ('עוגת שוקולד', 'קינוחים', 'item', 'עוגה ל-12 סועדים', 12000, 83, 83, 1000, 1000, 'dairy', true, false, 'categories/food-dessert.webp', true, 1, null),
  ('מגש פירות העונה', 'קינוחים', 'tray', 'מגש ל-15 סועדים', 16000, 67, 67, 1000, 1000, 'pareve', true, true, 'categories/food-dessert.webp', true, 2, null),
  ('טירמיסו', 'קינוחים', 'tray', 'מגש ל-12 סועדים', 18500, 83, 0, 1000, 1000, 'dairy', true, false, 'categories/food-dessert.webp', false, 3, 'לא זמין כרגע'),
  ('לימונדה ביתית', 'שתייה', 'item', 'קנקן 1.5 ליטר', 3500, 250, 250, 1000, 1000, 'pareve', true, true, 'categories/food-lemonade.webp', true, 1, null),
  ('מים מינרליים', 'שתייה', 'item', 'בקבוק 1.5 ליטר', 800, 330, 330, 1000, 1000, 'pareve', true, true, 'categories/food-lemonade.webp', true, 2, null)
) as v(name, cat, unit, unit_label, price, adult, child, step, min_qty, kashrut, veg, vegan, image, available, sort, descr)
join categories c on c.name = v.cat;

-- A missing row means "unknown" (e.g. סלט עונתי של השף, פטריות ממולאות have none on purpose).
insert into dish_allergens (dish_id, allergen_id, status)
select d.id, a.id, v.status::allergen_status
from (values
  ('סלט קינואה וירקות קלויים', 'שומשום', 'may_contain'),
  ('סלט קינואה וירקות קלויים', 'גלוטן', 'free'),
  ('טבולה', 'גלוטן', 'contains'),
  ('סלט יווני עם פטה', 'חלב', 'contains'),
  ('סלט ירוק גדול', 'גלוטן', 'free'),
  ('סלט ירוק גדול', 'חרדל', 'contains'),
  ('מיני פריקסה', 'גלוטן', 'contains'),
  ('מיני פריקסה', 'ביצים', 'contains'),
  ('מיני פריקסה', 'דגים', 'contains'),
  ('קנאפה סלמון מעושן', 'חלב', 'contains'),
  ('קנאפה סלמון מעושן', 'דגים', 'contains'),
  ('קנאפה סלמון מעושן', 'גלוטן', 'contains'),
  ('בורקס גבינה', 'גלוטן', 'contains'),
  ('בורקס גבינה', 'חלב', 'contains'),
  ('בורקס גבינה', 'ביצים', 'contains'),
  ('בורקס גבינה', 'שומשום', 'may_contain'),
  ('סלמון בתנור', 'דגים', 'contains'),
  ('דג לברק בעשבי תיבול', 'דגים', 'contains'),
  ('קציצות בקר ברוטב עגבניות', 'ביצים', 'contains'),
  ('קציצות בקר ברוטב עגבניות', 'גלוטן', 'may_contain'),
  ('עוף בגריל בסילאן', 'שומשום', 'contains'),
  ('לזניה ירקות', 'גלוטן', 'contains'),
  ('לזניה ירקות', 'חלב', 'contains'),
  ('לזניה ירקות', 'ביצים', 'contains'),
  ('שניצלונים', 'גלוטן', 'contains'),
  ('שניצלונים', 'ביצים', 'contains'),
  ('שניצלונים', 'שומשום', 'may_contain'),
  ('אורז פרסי', 'גלוטן', 'free'),
  ('חלה מתוקה', 'גלוטן', 'contains'),
  ('חלה מתוקה', 'ביצים', 'contains'),
  ('חלה מתוקה', 'שומשום', 'may_contain'),
  ('לחמניות שאור', 'גלוטן', 'contains'),
  ('עוגת שוקולד', 'גלוטן', 'contains'),
  ('עוגת שוקולד', 'חלב', 'contains'),
  ('עוגת שוקולד', 'ביצים', 'contains'),
  ('עוגת שוקולד', 'אגוזים', 'may_contain'),
  ('טירמיסו', 'חלב', 'contains'),
  ('טירמיסו', 'ביצים', 'contains'),
  ('טירמיסו', 'גלוטן', 'contains')
) as v(dish, allergen, status)
join dishes d on d.name = v.dish
join allergens a on a.name = v.allergen;

update dishes
set allergens_verified_by = (select id from staff_users limit 1),
    allergens_verified_at = now() - interval '2 days'
where name in ('סלט ירוק גדול', 'בורקס גבינה', 'עוגת שוקולד', 'סלמון בתנור');

-- Delivery and availability ----------------------------------------------------
insert into delivery_zones (name, fee_agorot, is_active) values
  ('מרכז', 6000, true), ('שרון', 9000, true), ('שפלה', 9000, true),
  ('ירושלים', 15000, true), ('צפון', 20000, false);

insert into zone_cities (city, zone_id)
select v.city, z.id
from (values
  ('תל אביב-יפו', 'מרכז'), ('רמת גן', 'מרכז'), ('גבעתיים', 'מרכז'), ('חולון', 'מרכז'),
  ('בת ים', 'מרכז'), ('בני ברק', 'מרכז'),
  ('הרצליה', 'שרון'), ('רעננה', 'שרון'), ('כפר סבא', 'שרון'), ('הוד השרון', 'שרון'), ('נתניה', 'שרון'),
  ('ראשון לציון', 'שפלה'), ('רחובות', 'שפלה'), ('נס ציונה', 'שפלה'), ('מודיעין-מכבים-רעות', 'שפלה'),
  ('ירושלים', 'ירושלים'), ('מבשרת ציון', 'ירושלים'),
  ('חיפה', 'צפון')
) as v(city, zone)
join delivery_zones z on z.name = v.zone;

-- weekday: 0 = Sunday ... 5 = Friday, null = every day
insert into time_slots (fulfillment, weekday, start_time, end_time) values
  ('pickup',   null, '10:00', '12:00'),
  ('pickup',   null, '12:00', '14:00'),
  ('pickup',   5,    '08:00', '11:00'),
  ('delivery', 0,    '11:00', '13:00'), ('delivery', 0, '17:00', '19:00'),
  ('delivery', 1,    '11:00', '13:00'), ('delivery', 1, '17:00', '19:00'),
  ('delivery', 2,    '11:00', '13:00'), ('delivery', 2, '17:00', '19:00'),
  ('delivery', 3,    '11:00', '13:00'), ('delivery', 3, '17:00', '19:00'),
  ('delivery', 4,    '11:00', '13:00'), ('delivery', 4, '17:00', '19:00'),
  ('delivery', 5,    '09:00', '12:00');

insert into calendar_overrides (date, max_guests, is_blocked, reason) values
  ('2026-11-20', null, true,  'חופשת צוות'),
  ('2026-12-04', 300,  false, 'חנוכה – צוות מורחב'),
  ('2026-12-11', 80,   false, 'שיפוץ חלקי במטבח');

-- Customers (all synthetic) ------------------------------------------------------
insert into customers (full_name, phone, email, auth_user_id) values
  ('לקוח דמו', '0500000000', 'demo.customer@example.com',
     (select id from auth.users where lower(email) = 'demo.customer@example.com')),
  ('נועה לוי',     '0500000001', 'noa.levi@example.com', null),
  ('יוסי כהן',     '0500000002', null, null),
  ('מיכל אברהם',   '0500000003', 'michal.a@example.com', null),
  ('דניאל מזרחי',  '0500000004', 'daniel.m@example.com', null),
  ('רותם פרץ',     '0500000005', null, null),
  ('אלון ביטון',   '0500000006', 'alon.b@example.com', null),
  ('שירה גולן',    '0500000007', 'shira.g@example.com', null);

-- Orders -------------------------------------------------------------------------
-- The access token hash stands in for the secret in each customer's private link.
create temp table demo_orders on commit drop as
select gen_random_uuid() as event_id, c.id as customer_id, v.*
from (values
  ('demo-order-1', '0500000000', 'pending_approval', 2, 'יום הולדת',          '2026-11-27', 30, 10, 4, 2, 0, null, 'delivery', 'תל אביב-יפו', 'רחוב הדוגמה 12, דירה 4', '2026-11-02 18:10+02'),
  ('demo-order-2', '0500000000', 'completed',        3, 'ארוחת שישי משפחתית', '2026-10-16', 12, 4, 0, 0, 0, null, 'pickup', null, null, '2026-10-05 12:00+03'),
  ('demo-order-3', '0500000000', 'draft',            3, 'מסיבת גן',            '2026-12-10', 20, 15, 3, 1, 1, 'ילד אחד אלרגי לאגוזים', 'delivery', 'רעננה', 'שדרות הדוגמה 3', '2026-11-04 21:30+02'),
  ('demo-order-4', '0500000001', 'approved',         4, 'בר/בת מצווה',         '2026-11-29', 80, 30, 10, 5, 2, 'שני אורחים ללא גלוטן', 'delivery', 'ירושלים', 'רחוב הניסיון 8', '2026-10-28 09:15+02'),
  ('demo-order-5', '0500000002', 'rejected',         3, 'יום נישואין',          '2026-11-22', 20, 0, 2, 0, 0, null, 'pickup', null, null, '2026-11-01 14:40+02'),
  ('demo-order-6', '0500000003', 'pending_approval', 2, 'שבת חתן',             '2026-12-04', 60, 20, 8, 3, 0, null, 'delivery', 'הרצליה', 'רחוב המבחן 21', '2026-11-04 10:05+02'),
  ('demo-order-7', '0500000004', 'cancelled',        3, 'ערב חברה',            '2026-11-19', 40, 0, 6, 4, 0, null, 'delivery', 'רמת גן', 'מגדל הדוגמה, קומה 7', '2026-10-30 16:20+02'),
  ('demo-order-8', '0500000005', 'approved',         4, 'ברית',                '2026-11-27', 50, 10, 5, 0, 0, null, 'delivery', 'ראשון לציון', 'רחוב הדמה 5', '2026-10-29 11:00+02')
) as v(token, phone, status, version, event_type, event_date, adults, children, veg, vegan,
       restricted, notes, fulfillment, city, address, created)
join customers c on c.phone = v.phone;

-- One event per demo order (an event may also have several orders).
insert into events (id, customer_id, event_type, event_date, adults, children,
                    vegetarian, vegan, restricted, dietary_notes, created_at)
select event_id, customer_id, event_type, event_date::date, adults, children,
       veg, vegan, restricted, notes, created::timestamptz
from demo_orders;

insert into orders (customer_id, event_id, access_token_hash, status, version,
                    time_slot_id, fulfillment, city, delivery_address, created_at)
select v.customer_id, v.event_id, encode(sha256(convert_to(v.token, 'UTF8')), 'hex'),
       v.status::order_status, v.version,
       (select s.id from time_slots s
         where s.fulfillment = v.fulfillment::fulfillment
           and (s.weekday = extract(dow from v.event_date::date) or s.weekday is null)
         order by s.weekday nulls last, s.start_time limit 1),
       v.fulfillment::fulfillment, v.city, v.address, v.created::timestamptz
from demo_orders v;

-- Order lines: (order token, dish, quantity in thousandths)
insert into order_items (order_id, dish_id, quantity_milli)
select o.id, d.id, v.qty
from (values
  ('demo-order-1', 'סלט ירוק גדול', 3000), ('demo-order-1', 'סלמון בתנור', 12500),
  ('demo-order-1', 'קציצות בקר ברוטב עגבניות', 2000), ('demo-order-1', 'בורקס גבינה', 60000),
  ('demo-order-1', 'לימונדה ביתית', 8000),
  ('demo-order-2', 'חלה מתוקה', 2000), ('demo-order-2', 'עוף בגריל בסילאן', 30000),
  ('demo-order-2', 'אורז פרסי', 20000), ('demo-order-2', 'סלט ירוק גדול', 2000),
  ('demo-order-3', 'שניצלונים', 40000), ('demo-order-3', 'תפוחי אדמה בתנור', 3000),
  ('demo-order-3', 'מגש פירות העונה', 2000), ('demo-order-3', 'לימונדה ביתית', 10000),
  ('demo-order-4', 'סלט קינואה וירקות קלויים', 8000), ('demo-order-4', 'טבולה', 6000),
  ('demo-order-4', 'עוף בגריל בסילאן', 160000), ('demo-order-4', 'קציצות בקר ברוטב עגבניות', 6000),
  ('demo-order-4', 'אורז פרסי', 120000), ('demo-order-4', 'ירקות קלויים', 6000),
  ('demo-order-4', 'מגש פירות העונה', 6000), ('demo-order-4', 'לחמניות שאור', 110000),
  ('demo-order-5', 'קנאפה סלמון מעושן', 40000), ('demo-order-5', 'סלט יווני עם פטה', 2000),
  ('demo-order-5', 'לזניה ירקות', 3000), ('demo-order-5', 'עוגת שוקולד', 2000),
  ('demo-order-6', 'מיני פריקסה', 120000), ('demo-order-6', 'דג לברק בעשבי תיבול', 90000),
  ('demo-order-6', 'סלט ירוק גדול', 6000), ('demo-order-6', 'חלה מתוקה', 10000),
  ('demo-order-6', 'ירקות קלויים', 5000),
  ('demo-order-7', 'פטריות ממולאות', 80000), ('demo-order-7', 'מגש אנטיפסטי אישי', 40000),
  ('demo-order-7', 'מים מינרליים', 14000),
  ('demo-order-8', 'בורקס גבינה', 100000), ('demo-order-8', 'סלמון בתנור', 60000),
  ('demo-order-8', 'לזניה ירקות', 5000), ('demo-order-8', 'עוגת שוקולד', 4000),
  ('demo-order-8', 'לימונדה ביתית', 15000)
) as v(token, dish, qty)
join orders o on o.access_token_hash = encode(sha256(convert_to(v.token, 'UTF8')), 'hex')
join dishes d on d.name = v.dish;

-- Freeze prices on every submitted order (what the backend does on submission).
-- Line total = quantity x price / 1000, rounded half up to the agora.
update order_items oi
set snapshot_name = d.name,
    snapshot_unit = d.unit,
    snapshot_kashrut = d.kashrut,
    snapshot_price_agorot = d.price_agorot,
    line_total_agorot = ((oi.quantity_milli::bigint * d.price_agorot + 500) / 1000)::int
from dishes d, orders o
where d.id = oi.dish_id and o.id = oi.order_id and o.status <> 'draft';

update orders o
set slot_start = s.start_time, slot_end = s.end_time
from time_slots s where s.id = o.time_slot_id;

update orders o
set delivery_fee_agorot = z.fee_agorot
from zone_cities zc join delivery_zones z on z.id = zc.zone_id
where o.city = zc.city and o.fulfillment = 'delivery' and o.status <> 'draft';

update orders o
set subtotal_agorot = t.subtotal,
    total_agorot    = t.subtotal + coalesce(o.delivery_fee_agorot, 0),
    vat_rate_bp     = 1800,
    -- VAT contained in a VAT-inclusive total, rounded half up
    vat_agorot      = (((t.subtotal + coalesce(o.delivery_fee_agorot, 0))::bigint * 1800 + 5900) / 11800)::int,
    submitted_at    = o.created_at + interval '20 minutes'
from (select order_id, sum(line_total_agorot)::int as subtotal
      from order_items group by order_id) t
where t.order_id = o.id and o.status <> 'draft';

-- Status history -----------------------------------------------------------------
insert into order_events (order_id, from_status, to_status, actor_type, created_at)
select id, null, 'draft'::order_status, 'customer'::actor_type, created_at from orders;

insert into order_events (order_id, from_status, to_status, actor_type, created_at)
select id, 'draft'::order_status, 'pending_approval'::order_status, 'customer'::actor_type, submitted_at
from orders where submitted_at is not null;

insert into order_events (order_id, from_status, to_status, actor_type, staff_user_id, note, created_at)
select o.id, 'pending_approval'::order_status, v.to_status::order_status, v.actor::actor_type,
       case when v.actor = 'staff' then (select id from staff_users limit 1) end,
       v.note, o.submitted_at + v.after::interval
from (values
  ('demo-order-2', 'approved',  'staff',    'מאושר. איסוף בשישי ב-10:00', '3 hours'),
  ('demo-order-4', 'approved',  'staff',    'מאושר. נשלח לווידוא כמויות ללא גלוטן', '1 day'),
  ('demo-order-5', 'rejected',  'staff',    'אין לנו מספיק צוות בתאריך הזה, מצטערים', '5 hours'),
  ('demo-order-7', 'cancelled', 'customer', 'האירוע בוטל', '2 days'),
  ('demo-order-8', 'approved',  'staff',    null, '6 hours')
) as v(token, to_status, actor, note, after)
join orders o on o.access_token_hash = encode(sha256(convert_to(v.token, 'UTF8')), 'hex');

insert into order_events (order_id, from_status, to_status, actor_type, note, created_at)
select o.id, 'approved'::order_status, 'completed'::order_status, 'system'::actor_type, 'האירוע הסתיים', e.event_date + interval '1 day'
from orders o join events e on e.id = o.event_id where o.status = 'completed';

-- AI assistant: a chat on the draft order with one pending suggestion ---------------
with o as (
  select id from orders
  where access_token_hash = encode(sha256(convert_to('demo-order-3', 'UTF8')), 'hex')
), conv as (
  insert into ai_conversations (order_id, created_at)
  select id, '2026-11-04 21:32+02' from o returning id, order_id
), msgs as (
  insert into ai_messages (conversation_id, role, content, created_at)
  select conv.id, m.role::message_role, m.content::jsonb, m.at::timestamptz
  from conv, (values
    ('user', '{"text":"יש לנו 15 ילדים, זה מספיק שניצלונים?"}', '2026-11-04 21:33+02'),
    ('assistant', '{"text":"ל-20 מבוגרים ו-15 ילדים אני ממליץ על 5 ק\"ג שניצלונים. כרגע יש 4 ק\"ג. להוסיף עוד קילו?"}', '2026-11-04 21:33+02'),
    ('user', '{"text":"כן, ותוסיף גם אורז"}', '2026-11-04 21:34+02')
  ) as m(role, content, at)
  returning 1
)
insert into ai_change_proposals (order_id, conversation_id, base_order_version, changes,
                                 price_before_agorot, price_after_agorot, status, created_at)
select conv.order_id, conv.id, 3,
       '[{"op":"set_quantity","dish":"שניצלונים","quantity_milli":50000},
         {"op":"add_item","dish":"אורז פרסי","quantity_milli":40000}]'::jsonb,
       -- before: 151,500 lines + 9,000 delivery; after: +1 kg schnitzel (14,000) + 4 kg rice (24,000)
       160500, 160500 + 14000 + 24000, 'pending'::proposal_status, '2026-11-04 21:34+02'
from conv;

commit;
