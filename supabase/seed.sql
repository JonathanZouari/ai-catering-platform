-- Synthetic data for the dev project. All people, addresses and prices are invented.
-- Requires demo users: run backend/scripts/create_demo_users.py first.
-- Load with: supabase db query --linked -f supabase/seed.sql

do $$
begin
  if exists (select 1 from public.dishes) then
    raise exception 'seed already loaded: public.dishes is not empty';
  end if;
  if not exists (select 1 from public.customers where email = 'demo@example.com') then
    raise exception 'run backend/scripts/create_demo_users.py first';
  end if;
end $$;

insert into public.dish_categories (name, sort_order) values
  ('סלטים ומטבלים', 1),
  ('עיקריות', 2),
  ('דגים', 3),
  ('תוספות ולחמים', 4),
  ('קינוחים', 5),
  ('שתייה', 6);

insert into public.allergens (name) values
  ('גלוטן'),
  ('אגוזים'),
  ('חלב'),
  ('ביצים'),
  ('שומשום'),
  ('דגים');

insert into public.dishes (category_id, name, description, pricing_unit, unit_price, unit_label)
select c.id, v.name, v.description, v.unit::public.pricing_unit, v.price, v.label
from (values
  ('סלטים ומטבלים', 'חומוס ביתי', 'חומוס חם עם טחינה גולמית, שמן זית ופפריקה.', 'per_tray', 85, 'מגש'),
  ('סלטים ומטבלים', 'סלט חצילים קלויים', 'חצילים שרופים על האש עם טחינה, לימון ופטרוזיליה.', 'per_tray', 90, 'מגש'),
  ('סלטים ומטבלים', 'סלט סלק וגבינת עיזים', 'סלק אפוי, גבינת עיזים, אגוזי מלך וויניגרט הדרים.', 'per_tray', 110, 'מגש'),
  ('סלטים ומטבלים', 'טבולה פטרוזיליה', 'פטרוזיליה קצוצה, בורגול, עגבניות ולימון.', 'per_tray', 80, 'מגש'),
  ('עיקריות', 'עוף בתנור בעשבי תיבול', 'ירכי עוף אפויות עם שום, רוזמרין ולימון.', 'per_weight', 74, 'ק״ג'),
  ('עיקריות', 'קציצות בקר ברוטב עגבניות', 'קציצות בקר רכות ברוטב עגבניות וכוסברה.', 'per_tray', 240, 'מגש'),
  ('עיקריות', 'פשטידת ברוקולי וגבינות', 'פשטידה אפויה עם ברוקולי ושלוש גבינות.', 'per_tray', 190, 'מגש'),
  ('עיקריות', 'תבשיל קדרה צמחי', 'ירקות עונה, חומוס ותבלינים בבישול איטי.', 'per_tray', 170, 'מגש'),
  ('דגים', 'פילה סלמון בלימון', 'פילה סלמון אפוי עם לימון, שמיר ושמן זית.', 'per_item', 98, 'יחידה'),
  ('דגים', 'דג מושט בצ׳רמולה', 'דג מושט שלם בתנור עם צ׳רמולה ביתית.', 'per_weight', 145, 'ק״ג'),
  ('תוספות ולחמים', 'אורז בסמטי ושקדים', 'אורז בסמטי עם שקדים קלויים ובצל מקורמל.', 'per_tray', 120, 'מגש'),
  ('תוספות ולחמים', 'ירקות שורש קלויים', 'גזר, בטטה וסלק קלויים עם דבש או סילאן.', 'per_tray', 105, 'מגש'),
  ('תוספות ולחמים', 'פוקאצ׳ה ביתית', 'פוקאצ׳ה אפויה עם רוזמרין ומלח גס.', 'per_item', 18, 'יחידה'),
  ('קינוחים', 'עוגת שוקולד ללא קמח', 'עוגת שוקולד מריר לחה, 12 פרוסות.', 'per_item', 160, 'יחידה'),
  ('קינוחים', 'פלטת פירות העונה', 'פירות טריים חתוכים, לכ-10 סועדים.', 'per_item', 140, 'יחידה'),
  ('קינוחים', 'מיני טארטלטים', 'טארטלטים עם קרם וניל ופירות יער.', 'per_item', 9, 'יחידה'),
  ('שתייה', 'שתייה קלה ומים', 'מבחר שתייה קלה ומים מינרליים לכל אורח.', 'per_guest', 14, 'לאורח')
) as v (category, name, description, unit, price, label)
join public.dish_categories c on c.name = v.category;

insert into public.dish_dietary (dish_id, kashrut_class, is_vegetarian, is_vegan, verified_at)
select d.id, v.kashrut::public.kashrut_class, v.vegetarian, v.vegan, now()
from (values
  ('חומוס ביתי', 'pareve', true, true),
  ('סלט חצילים קלויים', 'pareve', true, true),
  ('סלט סלק וגבינת עיזים', 'dairy', true, false),
  ('טבולה פטרוזיליה', 'pareve', true, true),
  ('עוף בתנור בעשבי תיבול', 'meat', false, false),
  ('קציצות בקר ברוטב עגבניות', 'meat', false, false),
  ('פשטידת ברוקולי וגבינות', 'dairy', true, false),
  ('תבשיל קדרה צמחי', 'pareve', true, true),
  ('פילה סלמון בלימון', 'pareve', false, false),
  ('דג מושט בצ׳רמולה', 'pareve', false, false),
  ('אורז בסמטי ושקדים', 'pareve', true, true),
  ('ירקות שורש קלויים', 'pareve', true, true),
  ('פוקאצ׳ה ביתית', 'pareve', true, true),
  ('עוגת שוקולד ללא קמח', 'pareve', true, false),
  ('פלטת פירות העונה', 'pareve', true, true),
  ('מיני טארטלטים', 'dairy', true, false),
  ('שתייה קלה ומים', 'pareve', true, true)
) as v (name, kashrut, vegetarian, vegan)
join public.dishes d on d.name = v.name;

-- 'תבשיל קדרה צמחי' intentionally has no rows: unknown is never "free".
insert into public.dish_allergens (dish_id, allergen_id, status)
select d.id, a.id, (case when a.name = any (v.contains) then 'contains' else 'free' end)::public.allergen_status
from (values
  ('חומוס ביתי', array['שומשום']::text[]),
  ('סלט חצילים קלויים', array[]::text[]),
  ('סלט סלק וגבינת עיזים', array['חלב', 'אגוזים']::text[]),
  ('טבולה פטרוזיליה', array['גלוטן']::text[]),
  ('עוף בתנור בעשבי תיבול', array[]::text[]),
  ('קציצות בקר ברוטב עגבניות', array['גלוטן', 'ביצים']::text[]),
  ('פשטידת ברוקולי וגבינות', array['חלב', 'גלוטן', 'ביצים']::text[]),
  ('פילה סלמון בלימון', array['דגים']::text[]),
  ('דג מושט בצ׳רמולה', array['דגים']::text[]),
  ('אורז בסמטי ושקדים', array['אגוזים']::text[]),
  ('ירקות שורש קלויים', array[]::text[]),
  ('פוקאצ׳ה ביתית', array['גלוטן']::text[]),
  ('עוגת שוקולד ללא קמח', array['ביצים', 'אגוזים']::text[]),
  ('פלטת פירות העונה', array[]::text[]),
  ('מיני טארטלטים', array['חלב', 'גלוטן', 'ביצים']::text[]),
  ('שתייה קלה ומים', array[]::text[])
) as v (name, contains)
join public.dishes d on d.name = v.name
cross join public.allergens a;

insert into public.delivery_zones (name, fee, definition) values
  ('תל אביב-יפו', 60, '{"city":"תל אביב-יפו"}'),
  ('רמת גן', 60, '{"city":"רמת גן"}'),
  ('גבעתיים', 60, '{"city":"גבעתיים"}'),
  ('הרצליה', 90, '{"city":"הרצליה"}'),
  ('פתח תקווה', 100, '{"city":"פתח תקווה"}'),
  ('ראשון לציון', 110, '{"city":"ראשון לציון"}');

insert into public.time_slots (fulfillment_type, start_time, end_time) values
  ('pickup', '10:00', '12:00'), ('pickup', '12:00', '14:00'), ('pickup', '15:00', '17:00'),
  ('delivery', '09:00', '11:00'), ('delivery', '11:00', '13:00'), ('delivery', '14:00', '16:00');

insert into public.blocked_dates (date, reason) values
  (current_date + 5, 'חופשת העסק'),
  (current_date + 11, 'אירוע גדול בתפוסה מלאה');

insert into public.customers (full_name, email, phone) values
  ('נועה לוי', 'noa.levi@example.com', '0500000001'),
  ('דן כהן', 'dan.cohen@example.com', '0500000002'),
  ('מאיה פרץ', 'maya.peretz@example.com', '0500000003'),
  ('יוסי מזרחי', 'yossi.mizrahi@example.com', '0500000004'),
  ('תמר אברהם', 'tamar.avraham@example.com', '0500000005');
update public.customers set phone = '0500000000' where email = 'demo@example.com';

do $$
declare
  r record;
  v_customer uuid;
  v_event uuid;
  v_order uuid;
  v_zone uuid;
  v_fee numeric(10,2);
  v_slot uuid;
  v_start time;
  v_subtotal numeric(10,2);
begin
  for r in select * from (values
    ('noa.levi@example.com', 'בר או בת מצווה', 21, 'pending_approval', 'delivery', 'תל אביב-יפו', 'רחוב הדוגמה 12', 60, 15, '{"חומוס ביתי":8,"קציצות בקר ברוטב עגבניות":6,"אורז בסמטי ושקדים":5,"פלטת פירות העונה":4}'::jsonb, null),
    ('dan.cohen@example.com', 'יום הולדת', 14, 'approved', 'pickup', null, null, 18, 4, '{"סלט חצילים קלויים":2,"עוף בתנור בעשבי תיבול":4,"ירקות שורש קלויים":2,"מיני טארטלטים":24}'::jsonb, 'ההזמנה אושרה. נתאם איתכם את שעת האיסוף.'),
    ('maya.peretz@example.com', 'ארוחת שבת', 9, 'rejected', 'delivery', 'רמת גן', 'שדרת הניסיון 7', 12, 6, '{"סלט סלק וגבינת עיזים":2,"פשטידת ברוקולי וגבינות":2,"עוגת שוקולד ללא קמח":1}'::jsonb, 'לא נוכל לספק מנות חלביות ובשריות באותו מועד. נשמח להציע תאריך חלופי.'),
    ('yossi.mizrahi@example.com', 'אירוע משפחתי', 30, 'pending_approval', 'delivery', 'הרצליה', 'רחוב הבדיקה 3', 40, 10, '{"חומוס ביתי":5,"פילה סלמון בלימון":25,"פוקאצ׳ה ביתית":60,"שתייה קלה ומים":50}'::jsonb, null),
    ('tamar.avraham@example.com', 'יום נישואין', 18, 'approved', 'pickup', null, null, 24, 0, '{"סלט חצילים קלויים":3,"דג מושט בצ׳רמולה":5,"אורז בסמטי ושקדים":3,"פלטת פירות העונה":3}'::jsonb, 'ההזמנה אושרה. תודה!'),
    ('demo@example.com', 'יום הולדת', 16, 'pending_approval', 'delivery', 'גבעתיים', 'רחוב הדמו 5', 20, 5, '{"חומוס ביתי":3,"עוף בתנור בעשבי תיבול":5,"פוקאצ׳ה ביתית":30,"פלטת פירות העונה":2}'::jsonb, null),
    ('demo@example.com', 'ארוחת שבת', 25, 'approved', 'pickup', null, null, 10, 2, '{"טבולה פטרוזיליה":2,"תבשיל קדרה צמחי":1,"ירקות שורש קלויים":1}'::jsonb, 'ההזמנה אושרה. נתראה באיסוף.')
  ) as t (email, event_type, days, status, fulfillment, city, address, adults, children, items, note)
  loop
    select id into v_customer from public.customers where email = r.email;
    select id, fee into v_zone, v_fee from public.delivery_zones where name = r.city;
    select id, start_time into v_slot, v_start from public.time_slots
    where fulfillment_type = r.fulfillment::public.fulfillment_type order by start_time limit 1;

    insert into public.events (customer_id, event_type, event_date, adults, children)
    values (v_customer, r.event_type, current_date + r.days, r.adults, r.children)
    returning id into v_event;

    insert into public.orders (customer_id, event_id, fulfillment_type, requested_at, time_slot_id,
                               delivery_address, delivery_zone_id)
    values (v_customer, v_event, r.fulfillment::public.fulfillment_type,
            ((current_date + r.days) + v_start) at time zone 'Asia/Jerusalem', v_slot,
            nullif(concat_ws(', ', r.address, r.city), ''), v_zone)
    returning id into v_order;

    insert into public.order_items (order_id, dish_id, quantity, snapshot_name, snapshot_pricing_unit,
                                    snapshot_unit_price, snapshot_line_total)
    select v_order, d.id, q.value::numeric, d.name, d.pricing_unit, d.unit_price, round(d.unit_price * q.value::numeric, 2)
    from jsonb_each_text(r.items) q join public.dishes d on d.name = q.key;

    select sum(snapshot_line_total) into v_subtotal from public.order_items where order_id = v_order;

    update public.orders
    set status = r.status::public.order_status, subtotal = v_subtotal, delivery_fee = coalesce(v_fee, 0),
        total = v_subtotal + coalesce(v_fee, 0), submitted_at = now() - interval '1 day', version = 2,
        decided_at = case when r.status in ('approved', 'rejected') then now() end,
        decision_note = r.note
    where id = v_order;
  end loop;
end $$;

-- One assistant conversation with a pending proposal on the demo customer's open order.
do $$
declare
  v_order uuid;
  v_total numeric(10,2);
  v_version int;
  v_conversation uuid;
  v_dish uuid;
  v_price numeric(10,2);
begin
  select o.id, o.total, o.version into v_order, v_total, v_version
  from public.orders o join public.customers c on c.id = o.customer_id
  where c.email = 'demo@example.com' and o.status = 'pending_approval';
  select id, unit_price into v_dish, v_price from public.dishes where name = 'ירקות שורש קלויים';

  insert into public.ai_conversations (order_id) values (v_order) returning id into v_conversation;
  insert into public.ai_messages (conversation_id, role, content) values
    (v_conversation, 'user', '{"text": "מה כדאי להוסיף לאירוע?"}'),
    (v_conversation, 'assistant', '{"text": "אפשר להוסיף ירקות שורש קלויים כתוספת. שום שינוי לא יתבצע בלי האישור שלכם."}');
  insert into public.ai_change_proposals (order_id, conversation_id, base_order_version, changes, price_before, price_after)
  values (v_order, v_conversation, v_version,
          jsonb_build_array(jsonb_build_object('op', 'add_item', 'dish_id', v_dish, 'quantity', 2)),
          v_total, v_total + v_price * 2);
end $$;

-- The account trigger cannot see app_metadata yet when the Admin API inserts a user, so remove the owner's row.
delete from public.customers where email = 'owner@example.com';
