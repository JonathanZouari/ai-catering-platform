-- Seed from frontend/customer/{index,menu}.html. Dietary/allergen flags intentionally not seeded (= unknown).

insert into event_types (code, label, sort_order) values
 ('bar-mitzvah','בר/בת מצווה',1),('shabbat','שבת',2),('birthday','יום הולדת',3),('family','ארוחה משפחתית',4),
 ('friends','מפגש חברים',5),('meat-party','מסיבת בשר',6),('kumsitz','קומזיץ',7),('proposal','הצעת נישואין',8),
 ('anniversary','יום נישואין',9),('brit','ברית',10),('housewarming','חנוכת בית',11),('reunion','מפגש מחזור',12);

insert into time_slots (start_time, end_time) values ('11:00','13:00'),('17:00','19:00'),('19:00','21:00');

insert into delivery_zones (name, fee) values ('משלוח רגיל', 120);

insert into dish_categories (name, sort_order) values
 ('ראשונות',1),('עיקריות',2),('תוספות',3),('סלטים',4),('קינוחים',5),
 ('משקאות',6),('יינות',7),('כלים',8),('אביזרים',9);

-- dishes: (category, kind, name, unit, price)
insert into dishes (category_id, kind, name, pricing_unit, unit_price)
select c.id, v.kind::dish_kind, v.name, v.unit::pricing_unit, v.price
from (values
 ('ראשונות','food','מגש מזה ים-תיכוני','per_guest',18),
 ('ראשונות','food','חצילים קלויים בטחינה','per_guest',16),
 ('ראשונות','food','קרפצ''יו סלק בשמן זית','per_guest',17),
 ('עיקריות','food','עוף בלימון וזיתים','per_guest',42),
 ('עיקריות','food','צלי בקר בפריסה','per_guest',52),
 ('עיקריות','food','דג לבן בלימון ועשבי תיבול','per_guest',46),
 ('תוספות','food','חלה מתוקה קלועה','per_guest',6),
 ('תוספות','food','ירקות צלויים במחבת','per_guest',12),
 ('תוספות','food','אורז בעשבי תיבול ושקדים','per_guest',10),
 ('סלטים','food','סלט טאבולה','per_guest',11),
 ('סלטים','food','סלט ירוק עם אבוקדו','per_guest',13),
 ('סלטים','food','סלט עגבניות ובזיליקום','per_guest',11),
 ('קינוחים','food','מגש טארטים ופרלינים','per_guest',16),
 ('קינוחים','food','טארט פירות','per_guest',18),
 ('קינוחים','food','מוס שוקולד ופטל','per_guest',15),
 ('משקאות','drink','לימונדה ביתית עם נענע','per_item',45),
 ('יינות','drink','יין אדום יבש','per_item',90),
 ('כלים','tools','ערכת כלים לסועד','per_guest',12),
 ('אביזרים','tools','בוצ''ר בלוק להגשה','per_item',60),
 -- per-cuisine drinks (offered with the whole-meal packages)
 ('משקאות','drink','יין לבן יבש','per_item',90),
 ('משקאות','drink','ערק עם לימון','per_item',120),
 ('משקאות','drink','יין אדום איטלקי','per_item',110),
 ('משקאות','drink','פרוסקו','per_item',95),
 ('משקאות','drink','מי סודה עם לימון','per_item',25),
 ('משקאות','drink','בירה מקסיקנית','per_item',18),
 ('משקאות','drink','טקילה','per_item',160),
 ('משקאות','drink','מי היביסקוס קרים','per_item',45),
 ('משקאות','drink','בירה תאילנדית','per_item',18),
 ('משקאות','drink','יין ריזלינג','per_item',100),
 ('משקאות','drink','תה קר בלמון-גראס','per_item',40)
) as v(cat, kind, name, unit, price)
join dish_categories c on c.name = v.cat;

insert into meal_packages (code, name, cuisine, description, price_per_guest) values
 ('med','ארוחה ים-תיכונית','ים-תיכוני','לימון, שמן זית ועשבי תיבול',95),
 ('ita','ארוחה איטלקית','איטלקי','עגבניות, בזיליקום וגבינות',110),
 ('mex','ארוחה מקסיקנית','מקסיקני','ליים, כוסברה ותירס',100),
 ('tha','ארוחה תאילנדית','תאילנדי','קוקוס, למון-גראס וליים',105);

insert into meal_package_drinks (package_id, dish_id)
select p.id, d.id
from (values
 ('med','יין לבן יבש'),('med','ערק עם לימון'),('med','לימונדה ביתית עם נענע'),
 ('ita','יין אדום איטלקי'),('ita','פרוסקו'),('ita','מי סודה עם לימון'),
 ('mex','בירה מקסיקנית'),('mex','טקילה'),('mex','מי היביסקוס קרים'),
 ('tha','בירה תאילנדית'),('tha','יין ריזלינג'),('tha','תה קר בלמון-גראס')
) as v(code, dish)
join meal_packages p on p.code = v.code
join dishes d on d.name = v.dish;
