-- Synthetic demo data. Safe to re-run only on an empty database (db reset / first push with --include-seed).
-- The two demo auth users are created separately; customers.auth_user_id is linked afterwards.

insert into dish_categories (name, sort_order) values
    ('סלטים ומטבלים', 1), ('עיקריות', 2), ('דגים', 3), ('תוספות ולחמים', 4), ('קינוחים', 5), ('שתייה', 6);

insert into allergens (name) values ('שומשום'), ('חלב'), ('אגוזים'), ('גלוטן'), ('ביצים'), ('דגים');

insert into dishes (category_id, name, description, pricing_unit, unit_price, quantity_step, per_guest_qty,
                    kashrut, is_vegetarian, is_vegan, allergens_verified)
select c.id, v.name, v.description, v.unit, v.price, v.step, v.per_guest, v.kashrut, v.veg, v.vegan, v.verified
from (values
 ('סלטים ומטבלים','חומוס ביתי','חומוס חם עם טחינה גולמית, שמן זית ופפריקה.','per_tray',85,1,null,'pareve',true,true,true),
 ('סלטים ומטבלים','סלט חצילים קלויים','חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.','per_tray',90,1,null,'pareve',true,true,true),
 ('סלטים ומטבלים','סלט סלק וגבינת עיזים','סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.','per_tray',110,1,null,'dairy',true,false,true),
 ('סלטים ומטבלים','טבולה פטרוזיליה','פטרוזיליה קצוצה, בורגול, עגבניות ולימון.','per_tray',80,1,null,'pareve',true,true,true),
 ('עיקריות','עוף בתנור בעשבי תיבול','ירכי עוף אפויות עם שום, רוזמרין ולימון.','per_weight',74,0.5,null,'meat',false,false,true),
 ('עיקריות','קציצות בקר ברוטב עגבניות','קציצות בקר רכות ברוטב עגבניות וכוסברה.','per_tray',240,1,null,'meat',false,false,true),
 ('עיקריות','פשטידת ברוקולי וגבינות','פשטידה אפויה עם ברוקולי ושלוש גבינות.','per_tray',190,1,null,'dairy',true,false,true),
 ('עיקריות','תבשיל קדרה צמחי','ירקות עונה, חומוס ותבלינים בבישול איטי.','per_tray',170,1,null,'pareve',true,true,false),
 ('דגים','פילה סלמון בלימון','פילה סלמון אפוי עם לימון, שמיר ושמן זית.','per_item',98,1,0.6,'pareve',false,false,true),
 ('דגים','דג מושט בצ׳רמולה','דג מושט שלם בתנור עם צ׳רמולה ביתית.','per_weight',145,0.5,null,'pareve',false,false,true),
 ('תוספות ולחמים','אורז בסמטי ושקדים','אורז בסמטי עם שקדים קלויים ובצל מקורמל.','per_tray',120,1,null,'pareve',true,true,true),
 ('תוספות ולחמים','ירקות שורש קלויים','גזר, בטטה וסלק קלויים עם דבש או סילאן.','per_tray',105,1,null,'pareve',true,true,true),
 ('תוספות ולחמים','פוקאצ׳ה ביתית','פוקאצ׳ה אפויה עם רוזמרין ומלח גס.','per_item',18,4,1.5,'pareve',true,true,true),
 ('קינוחים','עוגת שוקולד ללא קמח','עוגת שוקולד מריר לחה, 12 פרוסות.','per_item',160,1,0.1,'pareve',true,false,true),
 ('קינוחים','פלטת פירות העונה','פירות טריים חתוכים, לכ-10 סועדים.','per_item',140,1,0.1,'pareve',true,true,true),
 ('קינוחים','מיני טארטלטים','טארטלטים עם קרם וניל ופירות יער.','per_item',9,6,2,'dairy',true,false,true),
 ('שתייה','שתייה קלה ומים','מבחר שתייה קלה ומים מינרליים לכל אורח.','per_guest',14,1,null,'pareve',true,true,true)
) as v(cat, name, description, unit, price, step, per_guest, kashrut, veg, vegan, verified)
join dish_categories c on c.name = v.cat;

insert into dish_allergens (dish_id, allergen_id)
select d.id, a.id
from (values
 ('חומוס ביתי','שומשום'),
 ('סלט סלק וגבינת עיזים','חלב'),('סלט סלק וגבינת עיזים','אגוזים'),
 ('טבולה פטרוזיליה','גלוטן'),
 ('קציצות בקר ברוטב עגבניות','גלוטן'),('קציצות בקר ברוטב עגבניות','ביצים'),
 ('פשטידת ברוקולי וגבינות','חלב'),('פשטידת ברוקולי וגבינות','גלוטן'),('פשטידת ברוקולי וגבינות','ביצים'),
 ('פילה סלמון בלימון','דגים'),('דג מושט בצ׳רמולה','דגים'),
 ('אורז בסמטי ושקדים','אגוזים'),
 ('פוקאצ׳ה ביתית','גלוטן'),
 ('עוגת שוקולד ללא קמח','ביצים'),('עוגת שוקולד ללא קמח','אגוזים'),
 ('מיני טארטלטים','חלב'),('מיני טארטלטים','גלוטן'),('מיני טארטלטים','ביצים')
) as v(dish, allergen)
join dishes d on d.name = v.dish
join allergens a on a.name = v.allergen;

insert into delivery_zones (city, fee) values
    ('תל אביב-יפו', 60), ('רמת גן', 60), ('גבעתיים', 60), ('הרצליה', 90), ('פתח תקווה', 100), ('ראשון לציון', 110);

insert into time_slots (fulfillment_type, start_time, end_time) values
    ('pickup', '10:00', '12:00'), ('pickup', '12:00', '14:00'), ('pickup', '15:00', '17:00'),
    ('delivery', '09:00', '11:00'), ('delivery', '11:00', '13:00'), ('delivery', '14:00', '16:00');

insert into blocked_dates (date, reason) values
    (current_date + 5, 'חופשה'), (current_date + 11, 'אירוע סגור');

insert into customers (full_name, phone, email) values
    ('דנה לוי',  '0501234567', 'demo-customer@example.com'),
    ('יוסי כהן', '0527654321', 'yossi.cohen@example.com'),
    ('נועה אברהם','0541112233', null);

insert into events (event_type, event_date, adults, children, vegetarian_guests, vegan_guests, restricted_guests, dietary_notes) values
    ('birthday',        current_date + 14, 20, 6, 3, 1, 0, null),                       -- 1: draft
    ('family_event',    current_date + 9,  30, 10, 4, 2, 1, 'אלרגיה לאגוזים אצל אורח אחד'), -- 2: pending
    ('shabbat_dinner',  current_date + 7,  14, 4, 0, 0, 0, null),                       -- 3: approved
    ('bar_bat_mitzvah', current_date + 20, 60, 25, 8, 3, 2, null),                      -- 4: rejected
    ('anniversary',     current_date + 3,  12, 0, 2, 0, 0, null);                       -- 5: approved (demo customer)

-- Orders. Draft: no customer, no totals. Submitted: complete, with frozen snapshots on the items.
insert into orders (id, customer_id, event_id, status, fulfillment_type, time_slot_id, delivery_zone_id, delivery_address,
                    subtotal, delivery_fee, total, submitted_at, decided_at, decision_note)
values
 ('11111111-1111-4111-8111-111111111111', null, 1, 'draft', 'pickup', null, null, null, null, null, null, null, null, null),
 ('22222222-2222-4222-8222-222222222222',
    (select id from customers where full_name = 'דנה לוי'), 2, 'pending_approval', 'delivery',
    (select id from time_slots where fulfillment_type = 'delivery' and start_time = '11:00'),
    (select id from delivery_zones where city = 'תל אביב-יפו'), 'רחוב דיזנגוף 100, תל אביב',
    1210, 60, 1270, now() - interval '3 hours', null, null),
 ('33333333-3333-4333-8333-333333333333',
    (select id from customers where full_name = 'יוסי כהן'), 3, 'approved', 'pickup',
    (select id from time_slots where fulfillment_type = 'pickup' and start_time = '12:00'),
    null, null,
    1022, 0, 1022, now() - interval '2 days', now() - interval '1 day', null),
 ('44444444-4444-4444-8444-444444444444',
    (select id from customers where full_name = 'נועה אברהם'), 4, 'rejected', 'delivery',
    (select id from time_slots where fulfillment_type = 'delivery' and start_time = '14:00'),
    (select id from delivery_zones where city = 'פתח תקווה'), 'רחוב ז׳בוטינסקי 20, פתח תקווה',
    1905, 100, 2005, now() - interval '4 days', now() - interval '3 days', 'התאריך תפוס, אפשר להציע תאריך חלופי'),
 ('55555555-5555-4555-8555-555555555555',
    (select id from customers where full_name = 'דנה לוי'), 5, 'approved', 'delivery',
    (select id from time_slots where fulfillment_type = 'delivery' and start_time = '09:00'),
    (select id from delivery_zones where city = 'רמת גן'), 'רחוב ביאליק 5, רמת גן',
    956, 60, 1016, now() - interval '5 days', now() - interval '4 days', null);

-- Items: (order, dish, quantity). Snapshots are filled for submitted orders from the live catalog.
insert into order_items (order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit, snapshot_unit_price, snapshot_line_total)
select v.order_id::uuid, d.id, v.qty,
       case when v.frozen then d.name end,
       case when v.frozen then d.pricing_unit end,
       case when v.frozen then d.unit_price end,
       case when v.frozen then (d.unit_price * v.qty)::integer end
from (values
 ('11111111-1111-4111-8111-111111111111','חומוס ביתי',2,false),
 ('11111111-1111-4111-8111-111111111111','עוף בתנור בעשבי תיבול',3,false),
 ('22222222-2222-4222-8222-222222222222','חומוס ביתי',2,true),
 ('22222222-2222-4222-8222-222222222222','קציצות בקר ברוטב עגבניות',2,true),
 ('22222222-2222-4222-8222-222222222222','אורז בסמטי ושקדים',2,true),
 ('22222222-2222-4222-8222-222222222222','עוגת שוקולד ללא קמח',2,true),
 ('33333333-3333-4333-8333-333333333333','עוף בתנור בעשבי תיבול',4,true),
 ('33333333-3333-4333-8333-333333333333','טבולה פטרוזיליה',2,true),
 ('33333333-3333-4333-8333-333333333333','פוקאצ׳ה ביתית',12,true),
 ('33333333-3333-4333-8333-333333333333','שתייה קלה ומים',25,true),
 ('44444444-4444-4444-8444-444444444444','פילה סלמון בלימון',15,true),
 ('44444444-4444-4444-8444-444444444444','דג מושט בצ׳רמולה',3,true),
 ('55555555-5555-4555-8555-555555555555','סלט סלק וגבינת עיזים',2,true),
 ('55555555-5555-4555-8555-555555555555','פשטידת ברוקולי וגבינות',2,true),
 ('55555555-5555-4555-8555-555555555555','מיני טארטלטים',24,true),
 ('55555555-5555-4555-8555-555555555555','פלטת פירות העונה',1,true)
) as v(order_id, dish, qty, frozen)
join dishes d on d.name = v.dish;

insert into ai_messages (order_id, role, content) values
 ('11111111-1111-4111-8111-111111111111', 'user',      '{"text": "אני מארגנת יום הולדת ל-26 איש, מה מומלץ?"}'),
 ('11111111-1111-4111-8111-111111111111', 'assistant', '{"text": "למספר כזה אני ממליץ על שלושה מגשי מטבלים ושלושה ק״ג עוף. להוסיף?"}'),
 ('11111111-1111-4111-8111-111111111111', 'tool',      '{"name": "propose_change", "result": "ok"}');

insert into ai_change_proposals (order_id, base_order_version, changes, price_before, price_after)
values ('11111111-1111-4111-8111-111111111111', 1,
        jsonb_build_array(jsonb_build_object('op', 'set_quantity',
            'dish_id', (select id from dishes where name = 'חומוס ביתי'), 'quantity', 3)),
        392, 477);
