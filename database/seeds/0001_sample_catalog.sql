-- SAMPLE DATA, not the business's real menu or prices.
-- Same dishes as frontend/js/customer/mock-backend.js so the UI can switch to the API unchanged.

INSERT INTO dish_categories (id, name, sort_order) VALUES
  (1, 'סלטים ומטבלים', 1),
  (2, 'עיקריות', 2),
  (3, 'דגים', 3),
  (4, 'תוספות ולחמים', 4),
  (5, 'קינוחים', 5),
  (6, 'שתייה', 6);

INSERT INTO allergens (id, name) VALUES
  (1, 'גלוטן'), (2, 'חלב'), (3, 'ביצים'), (4, 'אגוזים'), (5, 'שומשום'), (6, 'דגים');

INSERT INTO dishes
  (id, category_id, name, description, pricing_unit, unit_price_minor, unit_label,
   kashrut_class, is_vegetarian, is_vegan)
VALUES
  (1, 1, 'חומוס ביתי', 'חומוס חם עם טחינה גולמית, שמן זית ופפריקה.', 'per_tray', 8500, 'מגש', 'pareve', 1, 1),
  (2, 1, 'סלט חצילים קלויים', 'חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.', 'per_tray', 9000, 'מגש', 'pareve', 1, 1),
  (3, 1, 'סלט סלק וגבינת עיזים', 'סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.', 'per_tray', 11000, 'מגש', 'dairy', 1, 0),
  (4, 1, 'טבולה פטרוזיליה', 'פטרוזיליה קצוצה, בורגול, עגבניות ולימון.', 'per_tray', 8000, 'מגש', 'pareve', 1, 1),
  (5, 2, 'עוף בתנור בעשבי תיבול', 'ירכי עוף אפויות עם שום, רוזמרין ולימון.', 'per_weight', 7400, 'ק״ג', 'meat', 0, 0),
  (6, 2, 'קציצות בקר ברוטב עגבניות', 'קציצות בקר רכות ברוטב עגבניות וכוסברה.', 'per_tray', 24000, 'מגש', 'meat', 0, 0),
  (7, 2, 'פשטידת ברוקולי וגבינות', 'פשטידה אפויה עם ברוקולי ושלוש גבינות.', 'per_tray', 19000, 'מגש', 'dairy', 1, 0),
  (8, 2, 'תבשיל קדרה צמחי', 'ירקות עונה, חומוס ותבלינים בבישול איטי.', 'per_tray', 17000, 'מגש', 'pareve', 1, 1),
  (9, 3, 'פילה סלמון בלימון', 'פילה סלמון אפוי עם לימון, שמיר ושמן זית.', 'per_item', 9800, 'יחידה', 'pareve', 0, 0),
  (10, 3, 'דג מושט בצ׳רמולה', 'דג מושט שלם בתנור עם צ׳רמולה ביתית.', 'per_weight', 14500, 'ק״ג', 'pareve', 0, 0),
  (11, 4, 'אורז בסמטי ושקדים', 'אורז בסמטי עם שקדים קלויים ובצל מקורמל.', 'per_tray', 12000, 'מגש', 'pareve', 1, 1),
  (12, 4, 'ירקות שורש קלויים', 'גזר, בטטה וסלק קלויים עם דבש או סילאן.', 'per_tray', 10500, 'מגש', 'pareve', 1, 1),
  (13, 4, 'פוקאצ׳ה ביתית', 'פוקאצ׳ה אפויה עם רוזמרין ומלח גס.', 'per_item', 1800, 'יחידה', 'pareve', 1, 1),
  (14, 5, 'עוגת שוקולד ללא קמח', 'עוגת שוקולד מריר לחה, 12 פרוסות.', 'per_item', 16000, 'יחידה', 'pareve', 1, 0),
  (15, 5, 'פלטת פירות העונה', 'פירות טריים חתוכים, לכ-10 סועדים.', 'per_item', 14000, 'יחידה', 'pareve', 1, 1),
  (16, 5, 'מיני טארטלטים', 'טארטלטים עם קרם וניל ופירות יער.', 'per_item', 900, 'יחידה', 'dairy', 1, 0),
  (17, 6, 'שתייה קלה ומים', 'מבחר שתייה קלה ומים מינרליים לכל אורח.', 'per_guest', 1400, 'לאורח', 'pareve', 1, 1);

-- Allergens each dish contains.
INSERT INTO dish_allergens (dish_id, allergen_id, status) VALUES
  (1, 5, 'contains'),
  (3, 2, 'contains'), (3, 4, 'contains'),
  (4, 1, 'contains'),
  (6, 1, 'contains'), (6, 3, 'contains'),
  (7, 2, 'contains'), (7, 1, 'contains'), (7, 3, 'contains'),
  (9, 6, 'contains'),
  (10, 6, 'contains'),
  (11, 4, 'contains'),
  (13, 1, 'contains'),
  (14, 3, 'contains'), (14, 4, 'contains'),
  (16, 2, 'contains'), (16, 1, 'contains'), (16, 3, 'contains');

-- Every other allergen is verified free, except dish 8, which has no allergen info (unknown).
INSERT INTO dish_allergens (dish_id, allergen_id, status)
SELECT d.id, a.id, 'free'
FROM dishes d CROSS JOIN allergens a
WHERE d.id <> 8
  AND NOT EXISTS (
    SELECT 1 FROM dish_allergens x WHERE x.dish_id = d.id AND x.allergen_id = a.id
  );
