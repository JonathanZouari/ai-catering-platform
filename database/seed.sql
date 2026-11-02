-- Seed data generated from frontend/js/customer/mock-backend.js (PLACEHOLDER business data, not real rules).
-- Run after schema.sql. Prices are converted from shekels to agorot. No admin user is seeded: create the owner
-- with a script that hashes the password (never commit credentials).

PRAGMA foreign_keys = ON;
BEGIN;

INSERT INTO business_settings (id, lead_days) VALUES (1, 2);  -- LEAD_DAYS, OPEN #5

INSERT INTO event_types (id, name, sort_order) VALUES
  (1, 'יום הולדת', 1),
  (2, 'אירוע משפחתי', 2),
  (3, 'בר או בת מצווה', 3),
  (4, 'ארוחת שבת', 4),
  (5, 'יום נישואין', 5),
  (6, 'חגיגה פרטית', 6),
  (7, 'אחר', 7);

INSERT INTO dish_categories (id, slug, name, sort_order) VALUES
  (1, 'salads', 'סלטים ומטבלים', 1),
  (2, 'mains', 'עיקריות', 2),
  (3, 'fish', 'דגים', 3),
  (4, 'sides', 'תוספות ולחמים', 4),
  (5, 'desserts', 'קינוחים', 5),
  (6, 'drinks', 'שתייה', 6);

INSERT INTO allergens (id, name) VALUES
  (1, 'שומשום'),
  (2, 'חלב'),
  (3, 'אגוזים'),
  (4, 'גלוטן'),
  (5, 'ביצים'),
  (6, 'דגים');

INSERT INTO dishes (id, category_id, name, description, pricing_unit, unit_price, qty_per_guest, step, kashrut, is_vegetarian, is_vegan, allergens_verified_at, sort_order) VALUES
  ('d1', 1, 'חומוס ביתי', 'חומוס חם עם טחינה גולמית, שמן זית ופפריקה.', 'tray', 8500, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 1),
  ('d2', 1, 'סלט חצילים קלויים', 'חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.', 'tray', 9000, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 2),
  ('d3', 1, 'סלט סלק וגבינת עיזים', 'סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.', 'tray', 11000, NULL, NULL, 'dairy', 1, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 3),
  ('d4', 1, 'טבולה פטרוזיליה', 'פטרוזיליה קצוצה, בורגול, עגבניות ולימון.', 'tray', 8000, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 4),
  ('d5', 2, 'עוף בתנור בעשבי תיבול', 'ירכי עוף אפויות עם שום, רוזמרין ולימון.', 'kg', 7400, NULL, NULL, 'meat', 0, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 5),
  ('d6', 2, 'קציצות בקר ברוטב עגבניות', 'קציצות בקר רכות ברוטב עגבניות וכוסברה.', 'tray', 24000, NULL, NULL, 'meat', 0, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 6),
  ('d7', 2, 'פשטידת ברוקולי וגבינות', 'פשטידה אפויה עם ברוקולי ושלוש גבינות.', 'tray', 19000, NULL, NULL, 'dairy', 1, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 7),
  ('d8', 2, 'תבשיל קדרה צמחי', 'ירקות עונה, חומוס ותבלינים בבישול איטי.', 'tray', 17000, NULL, NULL, 'pareve', 1, 1, NULL, 8),
  ('d9', 3, 'פילה סלמון בלימון', 'פילה סלמון אפוי עם לימון, שמיר ושמן זית.', 'item', 9800, 0.6, 1, 'pareve', 0, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 9),
  ('d10', 3, 'דג מושט בצ׳רמולה', 'דג מושט שלם בתנור עם צ׳רמולה ביתית.', 'kg', 14500, NULL, NULL, 'pareve', 0, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 10),
  ('d11', 4, 'אורז בסמטי ושקדים', 'אורז בסמטי עם שקדים קלויים ובצל מקורמל.', 'tray', 12000, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 11),
  ('d12', 4, 'ירקות שורש קלויים', 'גזר, בטטה וסלק קלויים עם דבש או סילאן.', 'tray', 10500, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 12),
  ('d13', 4, 'פוקאצ׳ה ביתית', 'פוקאצ׳ה אפויה עם רוזמרין ומלח גס.', 'item', 1800, 1.5, 4, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 13),
  ('d14', 5, 'עוגת שוקולד ללא קמח', 'עוגת שוקולד מריר לחה, 12 פרוסות.', 'item', 16000, 0.1, 1, 'pareve', 1, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 14),
  ('d15', 5, 'פלטת פירות העונה', 'פירות טריים חתוכים, לכ-10 סועדים.', 'item', 14000, 0.1, 1, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 15),
  ('d16', 5, 'מיני טארטלטים', 'טארטלטים עם קרם וניל ופירות יער.', 'item', 900, 2, 6, 'dairy', 1, 0, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 16),
  ('d17', 6, 'שתייה קלה ומים', 'מבחר שתייה קלה ומים מינרליים לכל אורח.', 'guest', 1400, NULL, NULL, 'pareve', 1, 1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 17);

INSERT INTO dish_allergens (dish_id, allergen_id) VALUES
  ('d1', 1),
  ('d3', 2),
  ('d3', 3),
  ('d4', 4),
  ('d6', 4),
  ('d6', 5),
  ('d7', 2),
  ('d7', 4),
  ('d7', 5),
  ('d9', 6),
  ('d10', 6),
  ('d11', 3),
  ('d13', 4),
  ('d14', 5),
  ('d14', 3),
  ('d16', 2),
  ('d16', 4),
  ('d16', 5);

INSERT INTO delivery_zones (id, city, fee) VALUES
  (1, 'תל אביב-יפו', 6000),
  (2, 'רמת גן', 6000),
  (3, 'גבעתיים', 6000),
  (4, 'הרצליה', 9000),
  (5, 'פתח תקווה', 10000),
  (6, 'ראשון לציון', 11000);

INSERT INTO time_slots (fulfillment, start_time, end_time) VALUES
  ('pickup', '10:00', '12:00'),
  ('pickup', '12:00', '14:00'),
  ('pickup', '15:00', '17:00'),
  ('delivery', '09:00', '11:00'),
  ('delivery', '11:00', '13:00'),
  ('delivery', '14:00', '16:00');

-- Demo only: the mock blocks "today + 5" and "today + 11". Replace with real closed dates.
INSERT INTO blocked_dates (date, reason) VALUES
  (date('now', '+5 days'), 'demo'),
  (date('now', '+11 days'), 'demo');

COMMIT;
