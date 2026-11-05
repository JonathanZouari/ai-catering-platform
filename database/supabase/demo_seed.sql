-- Synthetic demo data for the dedicated `cateringproject` Supabase project. Fake people only
-- (@example.com). Applied BY HAND after `python -m app.migrate`, never by the migration runner and
-- never by the tests:  psql "$DATABASE_URL" -f database/supabase/demo_seed.sql
-- Safe to re-run (fixed ids, ON CONFLICT DO NOTHING). customers.auth_user_id for
-- customer@example.com is linked by scripts/supabase_demo_users.py after the Auth user exists.
BEGIN;

INSERT INTO dish_categories (id, name_he, name_ar, name_en, sort_order) VALUES
  ('c0000000-0000-4000-8000-000000000001', 'סלטים', 'سلطات', 'Salads', 1),
  ('c0000000-0000-4000-8000-000000000002', 'עיקריות', 'أطباق رئيسية', 'Mains', 2),
  ('c0000000-0000-4000-8000-000000000003', 'תוספות', 'إضافات', 'Sides', 3),
  ('c0000000-0000-4000-8000-000000000004', 'דגים', 'أسماك', 'Fish', 4),
  ('c0000000-0000-4000-8000-000000000005', 'קינוחים', 'حلويات', 'Desserts', 5),
  ('c0000000-0000-4000-8000-000000000006', 'משקאות', 'مشروبات', 'Drinks', 6)
ON CONFLICT DO NOTHING;

INSERT INTO dishes (id, category_id, name_he, name_ar, name_en, description_he, description_en,
  pricing_unit, unit_price, unit_label, min_quantity, currency) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'c0000000-0000-4000-8000-000000000001', 'סלט ירקות', 'سلطة خضار', 'Garden salad', 'ירקות טריים חתוכים דק', 'Fresh finely chopped vegetables', 'per_tray', 90, 'מגש', NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000002', 'c0000000-0000-4000-8000-000000000001', 'חומוס', 'حمص', 'Hummus', 'חומוס ביתי עם טחינה', 'Home-made hummus with tahini', 'per_tray', 70, 'מגש', NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000003', 'c0000000-0000-4000-8000-000000000002', 'שניצל', 'شنيتسل', 'Schnitzel', 'חזה עוף בציפוי פירורי לחם', 'Breaded chicken breast', 'per_tray', 120, 'מגש', 2, 'ILS'),
  ('d0000000-0000-4000-8000-000000000004', 'c0000000-0000-4000-8000-000000000002', 'פרגיות על האש', 'دجاج مشوي', 'Grilled chicken thighs', NULL, NULL, 'per_weight', 140, 'ק"ג', 1, 'ILS'),
  ('d0000000-0000-4000-8000-000000000005', 'c0000000-0000-4000-8000-000000000003', 'אורז לבן', 'أرز أبيض', 'White rice', NULL, NULL, 'per_tray', 60, 'מגש', NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000006', 'c0000000-0000-4000-8000-000000000005', 'עוגת שוקולד', 'كعكة شوكولاتة', 'Chocolate cake', NULL, NULL, 'per_item', 85, 'עוגה', NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000007', 'c0000000-0000-4000-8000-000000000005', 'סלט פירות', 'سلطة فواكه', 'Fruit salad', NULL, NULL, 'per_guest', 12, NULL, NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000008', 'c0000000-0000-4000-8000-000000000004', 'סלמון בתנור', 'سلمون مشوي', 'Baked salmon', 'פילה סלמון עם עשבי תיבול', 'Salmon fillet with herbs', 'per_tray', 220, 'מגש', NULL, 'ILS'),
  ('d0000000-0000-4000-8000-000000000009', 'c0000000-0000-4000-8000-000000000006', 'לימונדה', 'ليموناضة', 'Lemonade', NULL, NULL, 'per_item', 18, 'בקבוק', NULL, 'ILS')
ON CONFLICT DO NOTHING;

-- Missing rows/NULLs mean "unknown" (never "no"): the rice and lemonade have no dietary row on purpose.
INSERT INTO dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan) VALUES
  ('d0000000-0000-4000-8000-000000000001', 'pareve', true, true),
  ('d0000000-0000-4000-8000-000000000002', 'pareve', true, true),
  ('d0000000-0000-4000-8000-000000000003', 'meat', false, false),
  ('d0000000-0000-4000-8000-000000000004', 'meat', false, false),
  ('d0000000-0000-4000-8000-000000000006', 'dairy', true, false),
  ('d0000000-0000-4000-8000-000000000007', 'pareve', true, true),
  ('d0000000-0000-4000-8000-000000000008', 'pareve', false, false)
ON CONFLICT DO NOTHING;

INSERT INTO dish_allergens (dish_id, allergen_id, status)
  SELECT v.d::uuid, a.id, v.s::allergen_status FROM (VALUES
    ('d0000000-0000-4000-8000-000000000002', 'sesame', 'contains'),
    ('d0000000-0000-4000-8000-000000000003', 'gluten', 'contains'),
    ('d0000000-0000-4000-8000-000000000003', 'eggs', 'contains'),
    ('d0000000-0000-4000-8000-000000000006', 'milk', 'contains'),
    ('d0000000-0000-4000-8000-000000000006', 'eggs', 'contains'),
    ('d0000000-0000-4000-8000-000000000006', 'gluten', 'contains'),
    ('d0000000-0000-4000-8000-000000000008', 'fish', 'contains'),
    ('d0000000-0000-4000-8000-000000000001', 'peanuts', 'free')
  ) AS v(d, n, s) JOIN allergens a ON a.name = v.n
ON CONFLICT DO NOTHING;

INSERT INTO quantity_rules (category_id, per_adult, per_child, round_step) VALUES
  ('c0000000-0000-4000-8000-000000000002', 0.1, 0.05, 1)
ON CONFLICT DO NOTHING;

INSERT INTO time_slots (id, fulfillment_type, start_time, end_time, capacity) VALUES
  ('e0000000-0000-4000-8000-000000000001', 'pickup', '12:00', '14:00', NULL),
  ('e0000000-0000-4000-8000-000000000002', 'delivery', '18:00', '20:00', 5)
ON CONFLICT DO NOTHING;

INSERT INTO delivery_zones (id, name, fee, definition) VALUES
  ('f0000000-0000-4000-8000-000000000001', 'ירושלים', 50, '{}')
ON CONFLICT DO NOTHING;

INSERT INTO blocked_dates (date, reason) VALUES ('2026-12-31', 'סגור לאירוע פרטי') ON CONFLICT DO NOTHING;

INSERT INTO business_settings (id) VALUES (true) ON CONFLICT DO NOTHING;

-- Nine orders, one per status. Orders 1, 5 and 9 belong to customer@example.com.
CREATE TEMP TABLE demo_orders ON COMMIT DROP AS
SELECT * FROM (VALUES
  (1, 'pending_approval', 'pickup',   'customer@example.com', 'לקוח דמו'),
  (2, 'approved',         'delivery', 'dana.demo@example.com', 'דנה כהן (דמו)'),
  (3, 'rejected',         'pickup',   'yossi.demo@example.com', 'יוסי לוי (דמו)'),
  (4, 'cancelled',        'pickup',   'noa.demo@example.com', 'נועה שחר (דמו)'),
  (5, 'in_kitchen',       'delivery', 'customer@example.com', 'לקוח דמו'),
  (6, 'out_for_delivery', 'delivery', 'sami.demo@example.com', 'סאמי חורי (דמו)'),
  (7, 'ready_for_pickup', 'pickup',   'lina.demo@example.com', 'לינא נאסר (דמו)'),
  (8, 'draft',            'pickup',   'omer.demo@example.com', 'עומר בר (דמו)'),
  (9, 'delivered',        'pickup',   'customer@example.com', 'לקוח דמו')
) AS t(n, status, ftype, email, full_name);

-- One customers row per email.
INSERT INTO customers (id, full_name, email)
  SELECT DISTINCT ON (email) ('10000000-0000-4000-8000-' || lpad(n::text, 12, '0'))::uuid, full_name, email
  FROM demo_orders ORDER BY email, n
ON CONFLICT DO NOTHING;

INSERT INTO events (id, customer_id, event_type, event_date, adults, children, vegetarian_guests, dietary_notes)
  SELECT ('20000000-0000-4000-8000-' || lpad(o.n::text, 12, '0'))::uuid, c.id,
         (ARRAY['birthday', 'family_celebration', 'bar_bat_mitzvah', 'shabbat', 'other'])[1 + o.n % 5],
         DATE '2026-11-20' + o.n, 20 + o.n, 5, 2, CASE WHEN o.n = 1 THEN 'בלי בוטנים בבקשה' END
  FROM demo_orders o JOIN customers c ON c.email = o.email
ON CONFLICT DO NOTHING;

-- access_token_hash is a hash of a random value nobody holds: demo orders have no private link.
INSERT INTO orders (id, customer_id, event_id, status, version, access_token_hash, fulfillment_type,
  time_slot_id, requested_at, delivery_address, delivery_zone_id, currency, subtotal, delivery_fee, total,
  submitted_at, first_submitted_at, decided_at, decision_note, cancelled_at, cancel_note,
  kitchen_at, dispatched_at, delivered_at)
  SELECT ('30000000-0000-4000-8000-' || lpad(o.n::text, 12, '0'))::uuid, c.id,
         ('20000000-0000-4000-8000-' || lpad(o.n::text, 12, '0'))::uuid,
         o.status::order_status, 2, encode(sha256(convert_to(gen_random_uuid()::text, 'UTF8')), 'hex'),
         o.ftype::fulfillment_type,
         CASE o.ftype WHEN 'pickup' THEN 'e0000000-0000-4000-8000-000000000001' ELSE 'e0000000-0000-4000-8000-000000000002' END::uuid,
         TIMESTAMPTZ '2026-11-20 10:00+02' + o.n * INTERVAL '1 day',
         CASE o.ftype WHEN 'delivery' THEN 'רחוב הרצל 1, ירושלים' END,
         CASE o.ftype WHEN 'delivery' THEN 'f0000000-0000-4000-8000-000000000001'::uuid END,
         'ILS', 625, CASE o.ftype WHEN 'delivery' THEN 50 ELSE 0 END, CASE o.ftype WHEN 'delivery' THEN 675 ELSE 625 END,
         CASE WHEN o.status <> 'draft' THEN now() - INTERVAL '3 days' END,
         CASE WHEN o.status <> 'draft' THEN now() - INTERVAL '3 days' END,
         CASE WHEN o.status NOT IN ('draft', 'pending_approval') THEN now() - INTERVAL '2 days' END,
         CASE o.status WHEN 'rejected' THEN 'לא ניתן לספק בתאריך זה' END,
         CASE o.status WHEN 'cancelled' THEN now() - INTERVAL '1 day' END,
         CASE o.status WHEN 'cancelled' THEN 'הלקוח ביטל בטלפון' END,
         CASE WHEN o.status IN ('in_kitchen', 'out_for_delivery', 'ready_for_pickup', 'delivered') THEN now() - INTERVAL '20 hours' END,
         CASE WHEN o.status IN ('out_for_delivery', 'ready_for_pickup', 'delivered') THEN now() - INTERVAL '10 hours' END,
         CASE WHEN o.status = 'delivered' THEN now() - INTERVAL '5 hours' END
  FROM demo_orders o JOIN customers c ON c.email = o.email
ON CONFLICT DO NOTHING;

-- 3 x Schnitzel + 2 x Garden salad + 1 x Chocolate cake on every order (= 625).
INSERT INTO order_items (order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total)
  SELECT ('30000000-0000-4000-8000-' || lpad(o.n::text, 12, '0'))::uuid, v.dish::uuid, v.q, v.name, v.unit::pricing_unit, v.price, v.q * v.price
  FROM demo_orders o, (VALUES
    ('d0000000-0000-4000-8000-000000000003', 3, 'שניצל', 'per_tray', 120),
    ('d0000000-0000-4000-8000-000000000001', 2, 'סלט ירקות', 'per_tray', 90),
    ('d0000000-0000-4000-8000-000000000006', 1, 'עוגת שוקולד', 'per_item', 85)
  ) AS v(dish, q, name, unit, price)
ON CONFLICT DO NOTHING;

INSERT INTO order_ratings (order_id, stars, comment)
  VALUES ('30000000-0000-4000-8000-000000000009', 5, 'האוכל היה מעולה (דמו)')
ON CONFLICT DO NOTHING;

COMMIT;
