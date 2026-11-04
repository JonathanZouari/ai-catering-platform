-- Complete submitted quotations without rewriting any existing records.
CREATE TABLE dishes (
    id TEXT PRIMARY KEY,
    metadata TEXT NOT NULL CHECK (json_valid(metadata)),
    price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
    step_milli INTEGER NOT NULL CHECK (step_milli > 0)
) STRICT;
CREATE TABLE delivery_zones (
    city TEXT PRIMARY KEY,
    fee_minor INTEGER NOT NULL CHECK (fee_minor >= 0)
) STRICT;
CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id),
    dish_id TEXT NOT NULL REFERENCES dishes(id),
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    quantity_milli INTEGER NOT NULL CHECK (quantity_milli > 0),
    unit_price_minor INTEGER NOT NULL CHECK (unit_price_minor >= 0),
    line_total_minor INTEGER NOT NULL CHECK (line_total_minor >= 0),
    PRIMARY KEY (order_id, dish_id)
) STRICT;
-- Hash of a client-generated random capability: both retry key and private retrieval credential.
-- The original request is retained for conflict detection and historical contact/event display.
CREATE TABLE order_submissions (
    token_hash TEXT PRIMARY KEY,
    order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    payload TEXT NOT NULL CHECK (json_valid(payload))
) STRICT;

-- Existing demonstration menu and rates; business approval is still required.
INSERT INTO dishes VALUES ('d1', '{"id":"d1","categoryId":"salads","name":"חומוס ביתי","description":"חומוס חם עם טחינה גולמית, שמן זית ופפריקה.","price":85,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["שומשום"]}', 8500, 1000);
INSERT INTO dishes VALUES ('d2', '{"id":"d2","categoryId":"salads","name":"סלט חצילים קלויים","description":"חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.","price":90,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 9000, 1000);
INSERT INTO dishes VALUES ('d3', '{"id":"d3","categoryId":"salads","name":"סלט סלק וגבינת עיזים","description":"סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.","price":110,"unit":"tray","kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","אגוזים"]}', 11000, 1000);
INSERT INTO dishes VALUES ('d4', '{"id":"d4","categoryId":"salads","name":"טבולה פטרוזיליה","description":"פטרוזיליה קצוצה, בורגול, עגבניות ולימון.","price":80,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["גלוטן"]}', 8000, 1000);
INSERT INTO dishes VALUES ('d5', '{"id":"d5","categoryId":"mains","name":"עוף בתנור בעשבי תיבול","description":"ירכי עוף אפויות עם שום, רוזמרין ולימון.","price":74,"unit":"kg","kashrut":"meat","vegetarian":false,"vegan":false,"allergens":[]}', 7400, 500);
INSERT INTO dishes VALUES ('d6', '{"id":"d6","categoryId":"mains","name":"קציצות בקר ברוטב עגבניות","description":"קציצות בקר רכות ברוטב עגבניות וכוסברה.","price":240,"unit":"tray","kashrut":"meat","vegetarian":false,"vegan":false,"allergens":["גלוטן","ביצים"]}', 24000, 1000);
INSERT INTO dishes VALUES ('d7', '{"id":"d7","categoryId":"mains","name":"פשטידת ברוקולי וגבינות","description":"פשטידה אפויה עם ברוקולי ושלוש גבינות.","price":190,"unit":"tray","kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","גלוטן","ביצים"]}', 19000, 1000);
INSERT INTO dishes VALUES ('d8', '{"id":"d8","categoryId":"mains","name":"תבשיל קדרה צמחי","description":"ירקות עונה, חומוס ותבלינים בבישול איטי.","price":170,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":null}', 17000, 1000);
INSERT INTO dishes VALUES ('d9', '{"id":"d9","categoryId":"fish","name":"פילה סלמון בלימון","description":"פילה סלמון אפוי עם לימון, שמיר ושמן זית.","price":98,"unit":"item","perGuest":0.6,"step":1,"kashrut":"pareve","vegetarian":false,"vegan":false,"allergens":["דגים"]}', 9800, 1000);
INSERT INTO dishes VALUES ('d10', '{"id":"d10","categoryId":"fish","name":"דג מושט בצ׳רמולה","description":"דג מושט שלם בתנור עם צ׳רמולה ביתית.","price":145,"unit":"kg","kashrut":"pareve","vegetarian":false,"vegan":false,"allergens":["דגים"]}', 14500, 500);
INSERT INTO dishes VALUES ('d11', '{"id":"d11","categoryId":"sides","name":"אורז בסמטי ושקדים","description":"אורז בסמטי עם שקדים קלויים ובצל מקורמל.","price":120,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["אגוזים"]}', 12000, 1000);
INSERT INTO dishes VALUES ('d12', '{"id":"d12","categoryId":"sides","name":"ירקות שורש קלויים","description":"גזר, בטטה וסלק קלויים עם דבש או סילאן.","price":105,"unit":"tray","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 10500, 1000);
INSERT INTO dishes VALUES ('d13', '{"id":"d13","categoryId":"sides","name":"פוקאצ׳ה ביתית","description":"פוקאצ׳ה אפויה עם רוזמרין ומלח גס.","price":18,"unit":"item","perGuest":1.5,"step":4,"kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":["גלוטן"]}', 1800, 4000);
INSERT INTO dishes VALUES ('d14', '{"id":"d14","categoryId":"desserts","name":"עוגת שוקולד ללא קמח","description":"עוגת שוקולד מריר לחה, 12 פרוסות.","price":160,"unit":"item","perGuest":0.1,"step":1,"kashrut":"pareve","vegetarian":true,"vegan":false,"allergens":["ביצים","אגוזים"]}', 16000, 1000);
INSERT INTO dishes VALUES ('d15', '{"id":"d15","categoryId":"desserts","name":"פלטת פירות העונה","description":"פירות טריים חתוכים, לכ-10 סועדים.","price":140,"unit":"item","perGuest":0.1,"step":1,"kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 14000, 1000);
INSERT INTO dishes VALUES ('d16', '{"id":"d16","categoryId":"desserts","name":"מיני טארטלטים","description":"טארטלטים עם קרם וניל ופירות יער.","price":9,"unit":"item","perGuest":2,"step":6,"kashrut":"dairy","vegetarian":true,"vegan":false,"allergens":["חלב","גלוטן","ביצים"]}', 900, 6000);
INSERT INTO dishes VALUES ('d17', '{"id":"d17","categoryId":"drinks","name":"שתייה קלה ומים","description":"מבחר שתייה קלה ומים מינרליים לכל אורח.","price":14,"unit":"guest","kashrut":"pareve","vegetarian":true,"vegan":true,"allergens":[]}', 1400, 1000);
INSERT INTO delivery_zones VALUES ('תל אביב-יפו', 6000);
INSERT INTO delivery_zones VALUES ('רמת גן', 6000);
INSERT INTO delivery_zones VALUES ('גבעתיים', 6000);
INSERT INTO delivery_zones VALUES ('הרצליה', 9000);
INSERT INTO delivery_zones VALUES ('פתח תקווה', 10000);
INSERT INTO delivery_zones VALUES ('ראשון לציון', 11000);
