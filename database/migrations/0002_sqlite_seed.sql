-- Initial catalog seed. INSERT OR IGNORE: reruns never overwrite later edits.

INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('salads', 'סלטים ומטבלים', 0);
INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('mains', 'עיקריות', 1);
INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('fish', 'דגים', 2);
INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('sides', 'תוספות ולחמים', 3);
INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('desserts', 'קינוחים', 4);
INSERT OR IGNORE INTO dish_categories (id, name, sort_order) VALUES ('drinks', 'שתייה', 5);

INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d1', 'salads', 'חומוס ביתי', 'חומוס חם עם טחינה גולמית, שמן זית ופפריקה.', 85, 'tray', NULL, NULL, 'pareve', 1, 1, '["שומשום"]', 1, 0);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d2', 'salads', 'סלט חצילים קלויים', 'חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.', 90, 'tray', NULL, NULL, 'pareve', 1, 1, '[]', 1, 1);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d3', 'salads', 'סלט סלק וגבינת עיזים', 'סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.', 110, 'tray', NULL, NULL, 'dairy', 1, 0, '["חלב","אגוזים"]', 1, 2);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d4', 'salads', 'טבולה פטרוזיליה', 'פטרוזיליה קצוצה, בורגול, עגבניות ולימון.', 80, 'tray', NULL, NULL, 'pareve', 1, 1, '["גלוטן"]', 1, 3);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d5', 'mains', 'עוף בתנור בעשבי תיבול', 'ירכי עוף אפויות עם שום, רוזמרין ולימון.', 74, 'kg', NULL, NULL, 'meat', 0, 0, '[]', 1, 4);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d6', 'mains', 'קציצות בקר ברוטב עגבניות', 'קציצות בקר רכות ברוטב עגבניות וכוסברה.', 240, 'tray', NULL, NULL, 'meat', 0, 0, '["גלוטן","ביצים"]', 1, 5);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d7', 'mains', 'פשטידת ברוקולי וגבינות', 'פשטידה אפויה עם ברוקולי ושלוש גבינות.', 190, 'tray', NULL, NULL, 'dairy', 1, 0, '["חלב","גלוטן","ביצים"]', 1, 6);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d8', 'mains', 'תבשיל קדרה צמחי', 'ירקות עונה, חומוס ותבלינים בבישול איטי.', 170, 'tray', NULL, NULL, 'pareve', 1, 1, NULL, 1, 7);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d9', 'fish', 'פילה סלמון בלימון', 'פילה סלמון אפוי עם לימון, שמיר ושמן זית.', 98, 'item', 0.6, 1, 'pareve', 0, 0, '["דגים"]', 1, 8);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d10', 'fish', 'דג מושט בצ׳רמולה', 'דג מושט שלם בתנור עם צ׳רמולה ביתית.', 145, 'kg', NULL, NULL, 'pareve', 0, 0, '["דגים"]', 1, 9);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d11', 'sides', 'אורז בסמטי ושקדים', 'אורז בסמטי עם שקדים קלויים ובצל מקורמל.', 120, 'tray', NULL, NULL, 'pareve', 1, 1, '["אגוזים"]', 1, 10);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d12', 'sides', 'ירקות שורש קלויים', 'גזר, בטטה וסלק קלויים עם דבש או סילאן.', 105, 'tray', NULL, NULL, 'pareve', 1, 1, '[]', 1, 11);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d13', 'sides', 'פוקאצ׳ה ביתית', 'פוקאצ׳ה אפויה עם רוזמרין ומלח גס.', 18, 'item', 1.5, 4, 'pareve', 1, 1, '["גלוטן"]', 1, 12);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d14', 'desserts', 'עוגת שוקולד ללא קמח', 'עוגת שוקולד מריר לחה, 12 פרוסות.', 160, 'item', 0.1, 1, 'pareve', 1, 0, '["ביצים","אגוזים"]', 1, 13);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d15', 'desserts', 'פלטת פירות העונה', 'פירות טריים חתוכים, לכ-10 סועדים.', 140, 'item', 0.1, 1, 'pareve', 1, 1, '[]', 1, 14);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d16', 'desserts', 'מיני טארטלטים', 'טארטלטים עם קרם וניל ופירות יער.', 9, 'item', 2, 6, 'dairy', 1, 0, '["חלב","גלוטן","ביצים"]', 1, 15);
INSERT OR IGNORE INTO dishes (id, category_id, name, description, price, unit, per_guest, step, kashrut, is_vegetarian, is_vegan, allergens, is_available, sort_order) VALUES ('d17', 'drinks', 'שתייה קלה ומים', 'מבחר שתייה קלה ומים מינרליים לכל אורח.', 14, 'guest', NULL, NULL, 'pareve', 1, 1, '[]', 1, 16);

INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('תל אביב-יפו', 60);
INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('רמת גן', 60);
INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('גבעתיים', 60);
INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('הרצליה', 90);
INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('פתח תקווה', 100);
INSERT OR IGNORE INTO delivery_zones (city, fee) VALUES ('ראשון לציון', 110);
