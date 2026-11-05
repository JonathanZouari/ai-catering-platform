-- Preserve historical submissions and receipts while normalizing the local fallback too.
CREATE TABLE dish_categories (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 sort_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
) STRICT;
INSERT INTO dish_categories(code,name)
SELECT DISTINCT json_extract(metadata,'$.categoryId'),json_extract(metadata,'$.categoryId') FROM dishes;
CREATE TABLE dishes_normalized (
 id INTEGER PRIMARY KEY, legacy_code TEXT NOT NULL UNIQUE,
 category_id INTEGER NOT NULL REFERENCES dish_categories(id),
 name TEXT NOT NULL CHECK(length(trim(name))>0), description TEXT,
 unit TEXT NOT NULL CHECK(unit IN ('tray','kg','item','guest')),
 price_minor INTEGER NOT NULL CHECK(price_minor>=0), step_milli INTEGER NOT NULL CHECK(step_milli>0),
 per_guest REAL CHECK(per_guest>0),
 is_available INTEGER NOT NULL DEFAULT 1 CHECK(is_available IN (0,1))
) STRICT;
CREATE INDEX dishes_category_idx ON dishes_normalized(category_id);
INSERT INTO dishes_normalized(legacy_code,category_id,name,description,unit,price_minor,step_milli,per_guest)
SELECT d.id,c.id,json_extract(d.metadata,'$.name'),json_extract(d.metadata,'$.description'),
 json_extract(d.metadata,'$.unit'),d.price_minor,d.step_milli,json_extract(d.metadata,'$.perGuest')
FROM dishes d JOIN dish_categories c ON c.code=json_extract(d.metadata,'$.categoryId')
ORDER BY length(d.id),d.id;
-- Immutable migration snapshot, not a catalog source and never returned by the API.
CREATE TABLE legacy_catalog_snapshot (
 id INTEGER PRIMARY KEY REFERENCES dishes_normalized(id), metadata TEXT NOT NULL CHECK(json_valid(metadata))
) STRICT;
INSERT INTO legacy_catalog_snapshot SELECT n.id,d.metadata FROM dishes d JOIN dishes_normalized n ON n.legacy_code=d.id;
CREATE TABLE dish_dietary (
 dish_id INTEGER PRIMARY KEY REFERENCES dishes_normalized(id),
 kashrut_class TEXT CHECK(kashrut_class IN ('meat','dairy','pareve')),
 is_vegetarian INTEGER CHECK(is_vegetarian IN (0,1)), is_vegan INTEGER CHECK(is_vegan IN (0,1)), verified_at TEXT
) STRICT;
INSERT INTO dish_dietary(dish_id,kashrut_class,is_vegetarian,is_vegan)
SELECT n.id,json_extract(d.metadata,'$.kashrut'),json_extract(d.metadata,'$.vegetarian'),json_extract(d.metadata,'$.vegan')
FROM dishes d JOIN dishes_normalized n ON n.legacy_code=d.id;
CREATE TABLE allergens (id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE) STRICT;
INSERT INTO allergens(name) SELECT DISTINCT a.value FROM dishes d,json_each(d.metadata,'$.allergens') a WHERE a.type='text';
CREATE TABLE dish_allergens (
 dish_id INTEGER NOT NULL REFERENCES dishes_normalized(id), allergen_id INTEGER NOT NULL REFERENCES allergens(id),
 status TEXT NOT NULL CHECK(status IN ('contains','free','unknown')), PRIMARY KEY(dish_id,allergen_id)
) STRICT;
CREATE INDEX dish_allergens_allergen_idx ON dish_allergens(allergen_id);
INSERT INTO dish_allergens
SELECT DISTINCT n.id,a.id,'contains' FROM dishes d JOIN dishes_normalized n ON n.legacy_code=d.id,
 json_each(d.metadata,'$.allergens') j JOIN allergens a ON a.name=j.value;
CREATE TABLE order_items_normalized (
 order_id INTEGER NOT NULL REFERENCES orders(id), dish_id INTEGER NOT NULL REFERENCES dishes_normalized(id),
 name TEXT NOT NULL,unit TEXT NOT NULL,quantity_milli INTEGER NOT NULL CHECK(quantity_milli>0),
 unit_price_minor INTEGER NOT NULL CHECK(unit_price_minor>=0),line_total_minor INTEGER NOT NULL CHECK(line_total_minor>=0),
 PRIMARY KEY(order_id,dish_id)
) STRICT;
INSERT INTO order_items_normalized SELECT i.order_id,n.id,i.name,i.unit,i.quantity_milli,i.unit_price_minor,i.line_total_minor
FROM order_items i JOIN dishes_normalized n ON n.legacy_code=i.dish_id;
DROP TABLE order_items;
DROP TABLE dishes;
ALTER TABLE dishes_normalized RENAME TO dishes;
ALTER TABLE order_items_normalized RENAME TO order_items;
CREATE INDEX order_items_dish_idx ON order_items(dish_id);
CREATE TABLE delivery_zones_normalized (
 id INTEGER PRIMARY KEY,city TEXT NOT NULL UNIQUE,fee_minor INTEGER NOT NULL CHECK(fee_minor>=0)
) STRICT;
INSERT INTO delivery_zones_normalized(city,fee_minor) SELECT city,fee_minor FROM delivery_zones ORDER BY rowid;
DROP TABLE delivery_zones;
ALTER TABLE delivery_zones_normalized RENAME TO delivery_zones;
CREATE TABLE order_submissions_normalized (
 token_hash TEXT NOT NULL UNIQUE,
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), payload TEXT NOT NULL CHECK(json_valid(payload))
) STRICT;
INSERT INTO order_submissions_normalized SELECT token_hash,order_id,payload FROM order_submissions;
DROP TABLE order_submissions;
ALTER TABLE order_submissions_normalized RENAME TO order_submissions;
