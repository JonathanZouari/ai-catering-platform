-- Sample data for practice. Readable IDs instead of UUIDs so queries are easy to type.
-- Category and dish IDs match the customer UI (illustrations and demo orders key on them).

INSERT INTO customers (id, full_name, email, phone) VALUES
    ('cust-1', 'נועה לוי', 'noa@example.com', '050-1234567'),
    ('cust-2', 'יוסי כהן', 'yossi@example.com', '052-7654321');

INSERT INTO events (id, customer_id, event_type, event_date, adults, children, vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) VALUES
    ('evt-1', 'cust-1', 'בר או בת מצווה', '2026-12-10', 30, 8, 4, 2, 1, 'אורח אחד עם אלרגיה לאגוזים'),
    ('evt-2', 'cust-2', 'יום הולדת', '2026-11-20', 25, 10, 4, 0, 0, NULL);

INSERT INTO dish_categories (id, name, sort_order) VALUES
    ('salads', 'סלטים ומטבלים', 1),
    ('mains', 'עיקריות', 2),
    ('fish', 'דגים', 3),
    ('sides', 'תוספות ולחמים', 4),
    ('desserts', 'קינוחים', 5),
    ('drinks', 'שתייה', 6);

INSERT INTO dishes (id, category_id, name, description, pricing_unit, unit_price, unit_label) VALUES
    ('d1', 'salads', 'חומוס ביתי', 'חומוס חם עם טחינה גולמית, שמן זית ופפריקה.', 'per_tray', 85, 'מגש'),
    ('d2', 'salads', 'סלט חצילים קלויים', 'חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.', 'per_tray', 90, 'מגש'),
    ('d3', 'salads', 'סלט סלק וגבינת עיזים', 'סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.', 'per_tray', 110, 'מגש'),
    ('d4', 'salads', 'טבולה פטרוזיליה', 'פטרוזיליה קצוצה, בורגול, עגבניות ולימון.', 'per_tray', 80, 'מגש'),
    ('d5', 'mains', 'עוף בתנור בעשבי תיבול', 'ירכי עוף אפויות עם שום, רוזמרין ולימון.', 'per_weight', 74, 'ק״ג'),
    ('d6', 'mains', 'קציצות בקר ברוטב עגבניות', 'קציצות בקר רכות ברוטב עגבניות וכוסברה.', 'per_tray', 240, 'מגש'),
    ('d7', 'mains', 'פשטידת ברוקולי וגבינות', 'פשטידה אפויה עם ברוקולי ושלוש גבינות.', 'per_tray', 190, 'מגש'),
    ('d8', 'mains', 'תבשיל קדרה צמחי', 'ירקות עונה, חומוס ותבלינים בבישול איטי.', 'per_tray', 170, 'מגש'),
    ('d9', 'fish', 'פילה סלמון בלימון', 'פילה סלמון אפוי עם לימון, שמיר ושמן זית.', 'per_item', 98, 'יחידה'),
    ('d10', 'fish', 'דג מושט בצ׳רמולה', 'דג מושט שלם בתנור עם צ׳רמולה ביתית.', 'per_weight', 145, 'ק״ג'),
    ('d11', 'sides', 'אורז בסמטי ושקדים', 'אורז בסמטי עם שקדים קלויים ובצל מקורמל.', 'per_tray', 120, 'מגש'),
    ('d12', 'sides', 'ירקות שורש קלויים', 'גזר, בטטה וסלק קלויים עם דבש או סילאן.', 'per_tray', 105, 'מגש'),
    ('d13', 'sides', 'פוקאצ׳ה ביתית', 'פוקאצ׳ה אפויה עם רוזמרין ומלח גס.', 'per_item', 18, 'יחידה'),
    ('d14', 'desserts', 'עוגת שוקולד ללא קמח', 'עוגת שוקולד מריר לחה, 12 פרוסות.', 'per_item', 160, 'יחידה'),
    ('d15', 'desserts', 'פלטת פירות העונה', 'פירות טריים חתוכים, לכ-10 סועדים.', 'per_item', 140, 'יחידה'),
    ('d16', 'desserts', 'מיני טארטלטים', 'טארטלטים עם קרם וניל ופירות יער.', 'per_item', 9, 'יחידה'),
    ('d17', 'drinks', 'שתייה קלה ומים', 'מבחר שתייה קלה ומים מינרליים לכל אורח.', 'per_guest', 14, 'לאורח');

INSERT INTO dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan, verified_at) VALUES
    ('d1', 'pareve', 1, 1, '2026-10-01'), ('d2', 'pareve', 1, 1, '2026-10-01'),
    ('d3', 'dairy', 1, 0, '2026-10-01'), ('d4', 'pareve', 1, 1, '2026-10-01'),
    ('d5', 'meat', 0, 0, '2026-10-01'), ('d6', 'meat', 0, 0, '2026-10-01'),
    ('d7', 'dairy', 1, 0, '2026-10-01'), ('d8', 'pareve', 1, 1, '2026-10-01'),
    ('d9', 'pareve', 0, 0, '2026-10-01'), ('d10', 'pareve', 0, 0, '2026-10-01'),
    ('d11', 'pareve', 1, 1, '2026-10-01'), ('d12', 'pareve', 1, 1, '2026-10-01'),
    ('d13', 'pareve', 1, 1, '2026-10-01'), ('d14', 'pareve', 1, 0, '2026-10-01'),
    ('d15', 'pareve', 1, 1, '2026-10-01'), ('d16', 'dairy', 1, 0, '2026-10-01'),
    ('d17', 'pareve', 1, 1, '2026-10-01');

INSERT INTO allergens (id, name) VALUES
    (1, 'גלוטן'), (2, 'אגוזים'), (3, 'חלב'), (4, 'ביצים'), (5, 'שומשום'), (6, 'דגים');

INSERT INTO dish_allergens (dish_id, allergen_id, status) VALUES
    ('d1', 5, 'contains'),
    ('d3', 3, 'contains'), ('d3', 2, 'contains'),
    ('d4', 1, 'contains'),
    ('d6', 1, 'contains'), ('d6', 4, 'contains'),
    ('d7', 3, 'contains'), ('d7', 1, 'contains'), ('d7', 4, 'contains'),
    ('d9', 6, 'contains'), ('d10', 6, 'contains'),
    ('d11', 2, 'contains'), ('d13', 1, 'contains'),
    ('d14', 4, 'contains'), ('d14', 2, 'contains'),
    ('d16', 3, 'contains'), ('d16', 1, 'contains'), ('d16', 4, 'contains');

-- Verified allergen-free dishes. d8 gets no rows on purpose: its allergens are "unknown".
INSERT INTO dish_allergens (dish_id, allergen_id, status)
SELECT v.column1, a.id, 'free'
FROM (VALUES ('d2'), ('d5'), ('d12'), ('d15'), ('d17')) AS v, allergens AS a;

INSERT INTO delivery_zones (id, name, fee, definition) VALUES
    ('zone-1', 'תל אביב והסביבה', 60, '{"cities": ["תל אביב-יפו", "רמת גן", "גבעתיים"]}'),
    ('zone-2', 'הרצליה', 90, '{"cities": ["הרצליה"]}'),
    ('zone-3', 'פתח תקווה', 100, '{"cities": ["פתח תקווה"]}'),
    ('zone-4', 'ראשון לציון', 110, '{"cities": ["ראשון לציון"]}');

INSERT INTO time_slots (id, fulfillment_type, start_time, end_time, capacity) VALUES
    ('slot-1', 'pickup', '10:00', '12:00', 5),
    ('slot-2', 'pickup', '12:00', '14:00', 5),
    ('slot-3', 'pickup', '15:00', '17:00', 5),
    ('slot-4', 'delivery', '09:00', '11:00', 3),
    ('slot-5', 'delivery', '11:00', '13:00', 3),
    ('slot-6', 'delivery', '14:00', '16:00', 3);

INSERT INTO blocked_dates (id, date, reason) VALUES
    ('blk-1', '2026-12-25', 'חופשת צוות');

-- order-1: still a draft, so prices are read live and snapshots stay empty.
INSERT INTO orders (id, customer_id, event_id, status, fulfillment_type, requested_at, delivery_address, delivery_zone_id) VALUES
    ('order-1', 'cust-1', 'evt-1', 'draft', 'delivery', '2026-12-10T11:30:00', 'רחוב אחד העם 12, תל אביב', 'zone-1');

INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES
    ('item-1', 'order-1', 'd1', 4),
    ('item-2', 'order-1', 'd5', 4),
    ('item-3', 'order-1', 'd15', 4);

-- order-2: submitted, so totals and line snapshots are frozen (drinks were cheaper back then).
INSERT INTO orders (id, customer_id, event_id, status, fulfillment_type, requested_at, subtotal, delivery_fee, total, submitted_at) VALUES
    ('order-2', 'cust-2', 'evt-2', 'pending_approval', 'pickup', '2026-11-20T12:00:00', 690, 0, 690, '2026-11-01T18:00:00');

INSERT INTO order_items (id, order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total) VALUES
    ('item-4', 'order-2', 'd2', 3, 'סלט חצילים קלויים', 'per_tray', 90, 270),
    ('item-5', 'order-2', 'd17', 35, 'שתייה קלה ומים', 'per_guest', 12, 420);

INSERT INTO ai_conversations (id, order_id) VALUES ('conv-1', 'order-1');

INSERT INTO ai_messages (id, conversation_id, role, content) VALUES
    ('msg-1', 'conv-1', 'user', '{"text": "יש לנו אורחים טבעונים, מה מתאים?"}'),
    ('msg-2', 'conv-1', 'assistant', '{"text": "תבשיל קדרה צמחי מסומן כטבעוני. להוסיף 3 מגשים?"}');

INSERT INTO ai_change_proposals (id, order_id, conversation_id, base_order_version, changes, price_before, price_after) VALUES
    ('prop-1', 'order-1', 'conv-1', 1, '[{"op": "add_item", "dish_id": "d8", "quantity": 3}]', 1196, 1706);
