-- SAMPLE DATA ONLY: invented dishes, prices and zones for local development.
-- Not real business data. Run after schema.sql.
-- Dietary/allergen facts are left unknown (NULL / no row) unless stated; unknown != free.

PRAGMA foreign_keys = ON;

INSERT INTO dish_categories (id, name, sort_order) VALUES
    ('cat-starters', 'Starters', 1),
    ('cat-salads',   'Salads', 2),
    ('cat-mains',    'Main courses', 3),
    ('cat-sides',    'Side dishes', 4),
    ('cat-desserts', 'Desserts', 5),
    ('cat-drinks',   'Drinks', 6);

INSERT INTO allergens (id, name) VALUES
    (1, 'Gluten'), (2, 'Tree nuts'), (3, 'Peanuts'), (4, 'Milk'), (5, 'Eggs'),
    (6, 'Sesame'), (7, 'Soy'), (8, 'Fish'), (9, 'Shellfish'), (10, 'Mustard');

INSERT INTO dishes (id, category_id, name, description, pricing_unit, unit_price, unit_label, min_quantity) VALUES
    ('d-hummus',   'cat-starters', 'Hummus platter',        'Classic hummus with olive oil',    'per_tray',  90, 'tray (10 servings)', 1),
    ('d-focaccia', 'cat-starters', 'Mini focaccia',         'Herb focaccia squares',            'per_item',   4, 'piece', 20),
    ('d-stuffed',  'cat-starters', 'Stuffed vine leaves',   'Rice-stuffed vine leaves',         'per_item',   3, 'piece', 20),
    ('d-greek',    'cat-salads',   'Greek salad',           'Tomato, cucumber, olives, feta',   'per_guest', 12, NULL, NULL),
    ('d-quinoa',   'cat-salads',   'Quinoa salad',          'Quinoa, herbs, lemon dressing',    'per_guest', 14, NULL, NULL),
    ('d-tabbouleh','cat-salads',   'Tabbouleh',             'Parsley and bulgur salad',         'per_tray',  80, 'tray (10 servings)', 1),
    ('d-chicken',  'cat-mains',    'Roasted chicken',       'Herb-roasted chicken pieces',      'per_guest', 38, NULL, NULL),
    ('d-salmon',   'cat-mains',    'Baked salmon',          'Salmon fillet with lemon',         'per_guest', 52, NULL, NULL),
    ('d-brisket',  'cat-mains',    'Slow-cooked brisket',   'Brisket in red wine sauce',        'per_weight',120, 'kg', 3),
    ('d-lasagna',  'cat-mains',    'Vegetable lasagna',     'Layered vegetables and cheese',    'per_tray', 220, 'tray (12 servings)', 1),
    ('d-rice',     'cat-sides',    'Herbed rice',           'Basmati rice with herbs',          'per_guest',  8, NULL, NULL),
    ('d-potatoes', 'cat-sides',    'Roasted potatoes',      'Rosemary roasted potatoes',        'per_weight', 35, 'kg', 2),
    ('d-brownie',  'cat-desserts', 'Brownie squares',       'Chocolate brownie',                'per_item',   6, 'piece', 20),
    ('d-fruit',    'cat-desserts', 'Seasonal fruit platter','Assorted cut fruit',               'per_tray', 150, 'tray (15 servings)', 1),
    ('d-lemonade', 'cat-drinks',   'Mint lemonade',         'Fresh lemonade with mint',         'per_item',  18, 'liter', 5);

-- Only a few dishes have verified dietary info; the rest have no row (= not provided).
INSERT INTO dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan, verified_at) VALUES
    ('d-hummus',    'pareve', 1, 1, '2026-11-01T00:00:00Z'),
    ('d-greek',     'dairy',  1, 0, '2026-11-01T00:00:00Z'),
    ('d-chicken',   'meat',   0, 0, '2026-11-01T00:00:00Z'),
    ('d-brisket',   'meat',   0, 0, '2026-11-01T00:00:00Z'),
    ('d-lasagna',   'dairy',  1, 0, '2026-11-01T00:00:00Z'),
    ('d-lemonade',  'pareve', 1, 1, '2026-11-01T00:00:00Z');
-- d-focaccia, d-stuffed, d-quinoa, d-tabbouleh, d-salmon, d-rice, d-potatoes, d-brownie, d-fruit: unknown.

-- Hummus: contains sesame, free of gluten/peanuts/milk. Lasagna: contains gluten and milk.
-- Every other allergen for these dishes, and all allergens for other dishes, stay unknown.
INSERT INTO dish_allergens (dish_id, allergen_id, status) VALUES
    ('d-hummus', 6, 'contains'), ('d-hummus', 1, 'free'), ('d-hummus', 3, 'free'), ('d-hummus', 4, 'free'),
    ('d-lasagna', 1, 'contains'), ('d-lasagna', 4, 'contains'),
    ('d-brownie', 1, 'unknown');

INSERT INTO delivery_zones (id, name, fee, definition) VALUES
    ('z-center', 'City center', 40, '{"type":"city_list","cities":["Tel Aviv"]}'),
    ('z-near',   'Nearby area',  70, '{"type":"city_list","cities":["Ramat Gan","Givatayim","Holon"]}'),
    ('z-far',    'Extended area',120, '{"type":"radius_km","max":40}');

INSERT INTO time_slots (id, fulfillment_type, weekday, start_time, end_time, capacity) VALUES
    ('ts-pick-sun', 'pickup',   0, '10:00', '14:00', NULL),
    ('ts-pick-thu', 'pickup',   4, '10:00', '14:00', NULL),
    ('ts-del-sun',  'delivery', 0, '11:00', '17:00', 10),
    ('ts-del-thu',  'delivery', 4, '11:00', '17:00', 10);

INSERT INTO blocked_dates (id, date, reason) VALUES
    ('b-1', '2026-12-25', 'Sample closed day');

-- Test data: one draft order and one order awaiting approval (prices snapshotted).
INSERT INTO customers (id, full_name, email, phone) VALUES
    ('c-1', 'Dana Sample', 'dana@example.com', '050-0000001'),
    ('c-2', 'Ron Sample',  'ron@example.com',  '050-0000002');

INSERT INTO events (id, customer_id, event_type, event_date, adults, children, vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) VALUES
    ('e-1', 'c-1', 'Birthday', '2026-12-10', 20, 5, 3, 1, 0, NULL),
    ('e-2', 'c-2', 'Office lunch', '2026-12-15', 30, 0, 4, 2, 1, 'One guest with a nut allergy (owner to review)');

INSERT INTO orders (id, customer_id, event_id, status, version, fulfillment_type, requested_at, delivery_address, delivery_zone_id, subtotal, delivery_fee, total, submitted_at) VALUES
    ('o-1', 'c-1', 'e-1', 'draft', 1, 'pickup', '2026-12-10T12:00:00Z', NULL, NULL, NULL, NULL, NULL, NULL),
    ('o-2', 'c-2', 'e-2', 'pending_approval', 2, 'delivery', '2026-12-15T12:00:00Z', 'Sample St 1, Tel Aviv', 'z-center', 1740, 40, 1780, '2026-11-02T09:00:00Z');

INSERT INTO order_items (id, order_id, dish_id, quantity) VALUES
    ('oi-1', 'o-1', 'd-hummus', 2),
    ('oi-2', 'o-1', 'd-chicken', 25);

INSERT INTO order_items (id, order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total) VALUES
    ('oi-3', 'o-2', 'd-chicken', 30, 'Roasted chicken', 'per_guest', 38, 1140),
    ('oi-4', 'o-2', 'd-greek',   30, 'Greek salad',     'per_guest', 12, 360),
    ('oi-5', 'o-2', 'd-rice',    30, 'Herbed rice',     'per_guest',  8, 240);
