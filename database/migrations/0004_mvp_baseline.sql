-- MVP-only baseline; existing legacy core rows are preserved.

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email       TEXT COLLATE NOCASE UNIQUE CHECK (email IS NULL OR email LIKE '%_@_%'),
    phone       TEXT CHECK (phone IS NULL OR length(trim(phone)) > 0),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    CHECK (email IS NOT NULL OR phone IS NOT NULL)
) STRICT;

CREATE TABLE IF NOT EXISTS addresses (
    id            INTEGER PRIMARY KEY,
    customer_id   INTEGER REFERENCES customers (id),
    label         TEXT,
    street        TEXT NOT NULL CHECK (length(trim(street)) > 0),
    house_number  TEXT,
    apartment     TEXT,
    floor         TEXT,
    city          TEXT NOT NULL CHECK (length(trim(city)) > 0),
    postal_code   TEXT,
    access_notes  TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                  CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                  CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    UNIQUE (id, customer_id)
) STRICT;

CREATE INDEX IF NOT EXISTS addresses_customer_id_idx ON addresses (customer_id);

CREATE TABLE IF NOT EXISTS events (
    id                 INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers (id),
    event_type         TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    event_date         TEXT NOT NULL CHECK (event_date IS date(event_date)),
    adults             INTEGER NOT NULL DEFAULT 0 CHECK (adults >= 0),
    children           INTEGER NOT NULL DEFAULT 0 CHECK (children >= 0),
    vegetarian_guests  INTEGER NOT NULL DEFAULT 0 CHECK (vegetarian_guests >= 0),
    vegan_guests       INTEGER NOT NULL DEFAULT 0 CHECK (vegan_guests >= 0),
    restricted_guests  INTEGER NOT NULL DEFAULT 0 CHECK (restricted_guests >= 0),
    dietary_notes      TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                       CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),
    CHECK (adults + children > 0),
    UNIQUE (id, customer_id)
) STRICT;

CREATE INDEX IF NOT EXISTS events_customer_id_idx ON events (customer_id);

CREATE TABLE IF NOT EXISTS orders (
    id                   INTEGER PRIMARY KEY,
    customer_id          INTEGER NOT NULL REFERENCES customers (id),
    event_id             INTEGER NOT NULL UNIQUE,
    status               TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'pending_approval', 'approved', 'rejected')),
    version              INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    fulfillment_type     TEXT NOT NULL CHECK (fulfillment_type IN ('pickup', 'delivery')),
    requested_at         TEXT NOT NULL
                         CHECK (requested_at IS strftime('%Y-%m-%dT%H:%M:%SZ', requested_at)),
    delivery_address_id  INTEGER,
    currency             TEXT NOT NULL DEFAULT 'ILS'
                         CHECK (length(currency) = 3 AND currency = upper(currency)),
    subtotal_minor       INTEGER CHECK (subtotal_minor IS NULL OR subtotal_minor >= 0),
    delivery_fee_minor   INTEGER CHECK (delivery_fee_minor IS NULL OR delivery_fee_minor >= 0),
    total_minor          INTEGER CHECK (total_minor IS NULL OR total_minor >= 0),
    submitted_at         TEXT CHECK (submitted_at IS NULL
                                     OR submitted_at IS strftime('%Y-%m-%dT%H:%M:%SZ', submitted_at)),
    decided_at           TEXT CHECK (decided_at IS NULL
                                     OR decided_at IS strftime('%Y-%m-%dT%H:%M:%SZ', decided_at)),
    decision_note        TEXT,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                         CHECK (created_at IS strftime('%Y-%m-%dT%H:%M:%SZ', created_at)),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
                         CHECK (updated_at IS strftime('%Y-%m-%dT%H:%M:%SZ', updated_at)),

    FOREIGN KEY (event_id, customer_id) REFERENCES events (id, customer_id),
    FOREIGN KEY (delivery_address_id, customer_id) REFERENCES addresses (id, customer_id),
    UNIQUE (id, currency),
    CHECK (fulfillment_type = 'delivery' OR delivery_address_id IS NULL),
    CHECK (fulfillment_type = 'delivery' OR delivery_fee_minor IS NULL OR delivery_fee_minor = 0),

    CHECK (status = 'draft' OR fulfillment_type = 'pickup' OR delivery_address_id IS NOT NULL),
    CHECK (status = 'draft' OR (subtotal_minor IS NOT NULL AND delivery_fee_minor IS NOT NULL
                                AND total_minor IS NOT NULL AND submitted_at IS NOT NULL)),
    CHECK (total_minor IS NULL OR (subtotal_minor IS NOT NULL AND delivery_fee_minor IS NOT NULL
                                   AND total_minor = subtotal_minor + delivery_fee_minor)),
    CHECK ((status IN ('approved', 'rejected')) = (decided_at IS NOT NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS orders_customer_id_idx ON orders (customer_id);

CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (status);

CREATE TRIGGER IF NOT EXISTS customers_touch AFTER UPDATE ON customers WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE customers SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS addresses_touch AFTER UPDATE ON addresses WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE addresses SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS events_touch AFTER UPDATE ON events WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE events SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS orders_touch AFTER UPDATE ON orders WHEN NEW.updated_at IS OLD.updated_at
BEGIN
    UPDATE orders SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = NEW.id;
END;

CREATE TABLE IF NOT EXISTS dishes (
    id TEXT PRIMARY KEY,
    metadata TEXT NOT NULL CHECK (json_valid(metadata)),
    price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
    step_milli INTEGER NOT NULL CHECK (step_milli > 0)
) STRICT;

CREATE TABLE IF NOT EXISTS delivery_zones (
    city TEXT PRIMARY KEY,
    fee_minor INTEGER NOT NULL CHECK (fee_minor >= 0)
) STRICT;

CREATE TABLE IF NOT EXISTS order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    dish_id TEXT NOT NULL REFERENCES dishes(id),
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    quantity_milli INTEGER NOT NULL CHECK (quantity_milli > 0),
    unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
    line_total_minor INTEGER NOT NULL CHECK (line_total_minor >= 0),
    PRIMARY KEY (order_id, dish_id)
) STRICT;

CREATE TABLE IF NOT EXISTS order_submissions (
    token_hash TEXT PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    payload TEXT NOT NULL CHECK (json_valid(payload))
) STRICT;

INSERT OR IGNORE INTO dishes VALUES ('d1', '{"id":"d1","categoryId":"salads","name":"חומוס ביתי","description":"חומוס חם עם טחינה גולמית, שמן זית ופפריקה.","price":85,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["שומשום"]}', 8500, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d2', '{"id":"d2","categoryId":"salads","name":"סלט חצילים קלויים","description":"חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.","price":90,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 9000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d3', '{"id":"d3","categoryId":"salads","name":"סלט סלק וגבינת עיזים","description":"סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.","price":110,"unit":"tray","kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","אגוזים"]}', 11000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d4', '{"id":"d4","categoryId":"salads","name":"טבולה פטרוזיליה","description":"פטרוזיליה קצוצה, בורגול, עגבניות ולימון.","price":80,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["גלוטן"]}', 8000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d5', '{"id":"d5","categoryId":"mains","name":"עוף בתנור בעשבי תיבול","description":"ירכי עוף אפויות עם שום, רוזמרין ולימון.","price":74,"unit":"kg","kashrut":"meat","vegetarian":false,"vegan":false,"allergens":[]}', 7400, 500);

INSERT OR IGNORE INTO dishes VALUES ('d6', '{"id":"d6","categoryId":"mains","name":"קציצות בקר ברוטב עגבניות","description":"קציצות בקר רכות ברוטב עגבניות וכוסברה.","price":240,"unit":"tray","kashrut":"meat","vegetarian":false,"vegan":false,"allergens":["גלוטן","ביצים"]}', 24000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d7', '{"id":"d7","categoryId":"mains","name":"פשטידת ברוקולי וגבינות","description":"פשטידה אפויה עם ברוקולי ושלוש גבינות.","price":190,"unit":"tray","kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","גלוטן","ביצים"]}', 19000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d8', '{"id":"d8","categoryId":"mains","name":"תבשיל קדרה צמחי","description":"ירקות עונה, חומוס ותבלינים בבישול איטי.","price":170,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":null}', 17000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d9', '{"id":"d9","categoryId":"fish","name":"פילה סלמון בלימון","description":"פילה סלמון אפוי עם לימון, שמיר ושמן זית.","price":98,"unit":"item","perGuest":0.6,"step":1,"kashrut":"pareve","vegetarian":false,"vegan":false,"allergens":["דגים"]}', 9800, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d10', '{"id":"d10","categoryId":"fish","name":"דג מושט בצ׳רמולה","description":"דג מושט שלם בתנור עם צ׳רמולה ביתית.","price":145,"unit":"kg","kashrut":"pareve","vegetarian":false,"vegan":false,"allergens":["דגים"]}', 14500, 500);

INSERT OR IGNORE INTO dishes VALUES ('d11', '{"id":"d11","categoryId":"sides","name":"אורז בסמטי ושקדים","description":"אורז בסמטי עם שקדים קלויים ובצל מקורמל.","price":120,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["אגוזים"]}', 12000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d12', '{"id":"d12","categoryId":"sides","name":"ירקות שורש קלויים","description":"גזר, בטטה וסלק קלויים עם דבש או סילאן.","price":105,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 10500, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d13', '{"id":"d13","categoryId":"sides","name":"פוקאצ׳ה ביתית","description":"פוקאצ׳ה אפויה עם רוזמרין ומלח גס.","price":18,"unit":"item","perGuest":1.5,"step":4,"kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["גלוטן"]}', 1800, 4000);

INSERT OR IGNORE INTO dishes VALUES ('d14', '{"id":"d14","categoryId":"desserts","name":"עוגת שוקולד ללא קמח","description":"עוגת שוקולד מריר לחה, 12 פרוסות.","price":160,"unit":"item","perGuest":0.1,"step":1,"kashrut":"pareve","vegetarian":true,"vegan":false,"allergens":["ביצים","אגוזים"]}', 16000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d15', '{"id":"d15","categoryId":"desserts","name":"פלטת פירות העונה","description":"פירות טריים חתוכים, לכ-10 סועדים.","price":140,"unit":"item","perGuest":0.1,"step":1,"kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 14000, 1000);

INSERT OR IGNORE INTO dishes VALUES ('d16', '{"id":"d16","categoryId":"desserts","name":"מיני טארטלטים","description":"טארטלטים עם קרם וניל ופירות יער.","price":9,"unit":"item","perGuest":2,"step":6,"kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","גלוטן","ביצים"]}', 900, 6000);

INSERT OR IGNORE INTO dishes VALUES ('d17', '{"id":"d17","categoryId":"drinks","name":"שתייה קלה ומים","description":"מבחר שתייה קלה ומים מינרליים לכל אורח.","price":14,"unit":"guest","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 1400, 1000);

INSERT OR IGNORE INTO delivery_zones VALUES ('תל אביב-יפו', 6000);

INSERT OR IGNORE INTO delivery_zones VALUES ('רמת גן', 6000);

INSERT OR IGNORE INTO delivery_zones VALUES ('גבעתיים', 6000);

INSERT OR IGNORE INTO delivery_zones VALUES ('הרצליה', 9000);

INSERT OR IGNORE INTO delivery_zones VALUES ('פתח תקווה', 10000);

INSERT OR IGNORE INTO delivery_zones VALUES ('ראשון לציון', 11000);
-- Only documented quotation transitions are permitted.
CREATE TRIGGER IF NOT EXISTS orders_status_transition
BEFORE UPDATE OF status ON orders
WHEN NEW.status IS NOT OLD.status
 AND NOT ((OLD.status = 'draft' AND NEW.status = 'pending_approval')
       OR (OLD.status = 'pending_approval' AND NEW.status IN ('approved', 'rejected')))
BEGIN
    SELECT RAISE(ABORT, 'invalid order status transition');
END;
