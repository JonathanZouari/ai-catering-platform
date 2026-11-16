-- Synthetic leads for testing the leads system (docs/LEADS_DESIGN.md). Not run automatically:
-- it is not listed in supabase/config.toml [db.seed].sql_paths. Run it by hand against a LOCAL or test database:
--   psql "$LOCAL_DB_URL" -f supabase/seed_leads.sql
-- Needs the migrations and supabase/seed.sql (event types, demo customer and order) to be applied first.
-- Safe to re-run: it removes the demo and history leads (ids 'demo-lead-%', 'hist-lead-%') and their events, then inserts them again.
-- All names, phones and emails are made up. Emails use example.com.
-- Two sets:
--   demo-lead-01..18   hand-written recent leads in every status (new 5, contacted 4, quoted 3, won 3, lost 3), with
--                      sample scores on the open ones so the admin UI has something to show.
--   hist-lead-001..150 generated history (won/lost only, last two years) to train the closing-probability model.
--                      Regenerate or resize with: python supabase/tools/gen_leads_history.py [--n 200]
-- The history is SYNTHETIC: win/lose follows a hand-written formula, so a model trained on it learns that formula,
-- not real customer behavior. Retrain on real closed leads before trusting any score.

begin;

delete from public.leads where id like 'demo-lead-%' or id like 'hist-lead-%';   -- lead_events go with them (on delete cascade)

insert into public.leads
  (id, full_name, phone, email, source, utm_source, utm_medium, utm_campaign, referrer,
   event_type_id, event_date, approx_guests, message, status, lost_reason,
   customer_id, order_id, consent_marketing, consent_at, created_at)
select v.id, v.full_name, v.phone, v.email, v.source, v.utm_source, v.utm_medium, v.utm_campaign, v.referrer,
       (select e.id from public.event_types e where e.name = v.event_type),
       case when v.days_ahead is null then null else current_date + v.days_ahead end,
       v.guests, v.message, v.status, v.lost_reason,
       (select c.id from public.customers c where c.id = v.customer_id),   -- null if the demo customer is missing
       (select o.id from public.orders o where o.id = v.order_id),         -- null if the demo order is missing
       v.consent, case when v.consent then now() - v.age else null end,
       now() - v.age
from (values
  -- ---- new (5): the first one is older than 24h, so the admin list should highlight it ----
  ('demo-lead-01','נועה לוי','+972500000001','noa.levi@example.com','landing_form','google','cpc','birthday-fall',null,
   'יום הולדת', 21, 25, 'מחפשת קייטרינג ליום הולדת 40, בעיקר סלטים ועיקריות.', 'new', null, null, null, true,  interval '30 hours'),
  ('demo-lead-02','איתי בן דוד','+972500000002',null,'landing_form','instagram','social','stories',null,
   'חתונה', 90, 180, null, 'new', null, null, null, false, interval '5 hours'),
  ('demo-lead-03','מיכל אברהם','+972500000003','michal.a@example.com','whatsapp',null,null,null,null,
   'אירוע חברה', 14, 60, 'ארוחת צהריים לצוות, יש כמה צמחונים.', 'new', null, null, null, false, interval '3 hours'),
  ('demo-lead-04','יוסי כץ','+972500000004',null,'abandoned_order',null,null,null,null,
   'בר/בת מצווה', 45, 70, null, 'new', null, null, null, false, interval '2 hours'),
  ('demo-lead-05','רונית שפירא','+972500000005','ronit.sh@example.com','ai_chat',null,null,null,null,
   null, null, 15, 'שאלה בצ''אט על כמויות לארוחת שישי.', 'new', null, null, null, true, interval '40 minutes'),

  -- ---- contacted (4) ----
  ('demo-lead-06','דן מזרחי','+972500000006','dan.m@example.com','landing_form','facebook','social','spring-offer',null,
   'יום הולדת', 30, 35, 'יום הולדת לילד, צריך גם מנות לילדים.', 'contacted', null, null, null, false, interval '2 days'),
  ('demo-lead-07','שירה גולן','+972500000007',null,'manual',null,null,null,null,
   'אירוע חברה', 25, 120, 'התקשרה לבעלים. מבקשת תפריט חלבי.', 'contacted', null, null, null, false, interval '3 days'),
  ('demo-lead-08','עמית פרידמן','+972500000008','amit.f@example.com','landing_form','google','organic',null,'https://www.google.com/',
   'חתונה', 120, 150, null, 'contacted', null, null, null, true, interval '4 days'),
  ('demo-lead-09','תמר חיים','+972500000009',null,'whatsapp',null,null,null,null,
   'בר/בת מצווה', 60, 90, 'ביקשה הצעה לשולחנות קבלת פנים.', 'contacted', null, null, null, false, interval '5 days'),

  -- ---- quoted (3) ----
  ('demo-lead-10','אורן סגל','+972500000010','oren.s@example.com','landing_form','newsletter','email','nov-menu',null,
   'אירוע חברה', 10, 45, 'ערב סיום פרויקט.', 'quoted', null, null, null, true, interval '6 days'),
  ('demo-lead-11','ליאת נחום','+972500000011',null,'abandoned_order',null,null,null,null,
   'יום הולדת', 12, 20, null, 'quoted', null, null, null, false, interval '7 days'),
  ('demo-lead-12','גיא רוזן','+972500000012','guy.r@example.com','manual',null,null,null,null,
   'חתונה', 150, 220, 'שולחן מתוקים גדול. הצעה נשלחה במייל.', 'quoted', null, null, null, false, interval '9 days'),

  -- ---- won (3): the first is linked to the demo customer and order from seed.sql ----
  ('demo-lead-13','דנה כהן','+972500000013','dana.c@example.com','landing_form','google','cpc','birthday-fall',null,
   'יום הולדת', 7, 25, 'יום הולדת עם 20 מבוגרים ו-5 ילדים.', 'won', null, 'demo-customer-1', 'demo-order-1', true, interval '12 days'),
  ('demo-lead-14','עידו אשכנזי','+972500000014',null,'whatsapp',null,null,null,null,
   'אירוע חברה', -10, 40, null, 'won', null, null, null, false, interval '20 days'),
  ('demo-lead-15','הדס ברק','+972500000015','hadas.b@example.com','ai_chat',null,null,null,null,
   'בר/בת מצווה', -20, 80, null, 'won', null, null, null, true, interval '30 days'),

  -- ---- lost (3) ----
  ('demo-lead-16','אלון פרץ','+972500000016',null,'landing_form','facebook','social','spring-offer',null,
   'חתונה', 200, 250, null, 'lost', 'המחיר גבוה מהתקציב', null, null, false, interval '25 days'),
  ('demo-lead-17','קרן מלכה','+972500000017','keren.m@example.com','manual',null,null,null,null,
   'יום הולדת', -5, 30, null, 'lost', 'בחרו קייטרינג אחר', null, null, false, interval '18 days'),
  ('demo-lead-18','בני אוחיון','+972500000018',null,'abandoned_order',null,null,null,null,
   'אירוע חברה', 3, 50, null, 'lost', 'לא ענה לאחר כמה ניסיונות', null, null, false, interval '15 days')
) as v(id, full_name, phone, email, source, utm_source, utm_medium, utm_campaign, referrer,
       event_type, days_ahead, guests, message, status, lost_reason, customer_id, order_id, consent, age);

-- Budget (agorot, total for the event) for the demo leads that gave a guest count: 90-120 per guest.
update public.leads
set budget_estimate = approx_guests * (9000 + (right(phone, 2)::int % 5) * 750)
where id like 'demo-lead-%' and approx_guests is not null and right(phone, 2)::int % 4 <> 0;

-- Sample scores for the open demo leads (placeholder values, NOT produced by a trained model).
update public.leads l
set conversion_probability = v.p,
    prediction_label = case when v.p >= 0.5 then 'won' else 'lost' end,
    prediction_model_version = 'demo-placeholder',
    predicted_at = now()
from (values ('demo-lead-01', 0.7100), ('demo-lead-02', 0.3200), ('demo-lead-03', 0.6400), ('demo-lead-04', 0.1800),
             ('demo-lead-05', 0.4400), ('demo-lead-06', 0.5800), ('demo-lead-07', 0.7700), ('demo-lead-08', 0.4100),
             ('demo-lead-09', 0.5200), ('demo-lead-10', 0.8300), ('demo-lead-11', 0.3600), ('demo-lead-12', 0.2900)
     ) as v(id, p)
where l.id = v.id;

-- Historical leads for model training.
-- BEGIN HISTORY (generated by supabase/tools/gen_leads_history.py)
-- 150 closed leads (won/lost) spread over the last two years. Phones +9725010xxxx, emails @example.com.
-- event_date is relative to the lead's own created_at (lead_days after it).
insert into public.leads
  (id, full_name, phone, email, source, utm_source, utm_medium, utm_campaign,
   event_type_id, event_date, approx_guests, budget_estimate, message, status, lost_reason,
   consent_marketing, consent_at, created_at)
select v.id, v.full_name, v.phone, v.email, v.source, v.utm_source, v.utm_medium, v.utm_campaign,
       (select e.id from public.event_types e where e.name = v.event_type),
       case when v.lead_days is null then null else (now() - v.age)::date + v.lead_days end,
       v.guests, v.budget, v.message, v.status, v.lost_reason,
       v.consent, case when v.consent then now() - v.age else null end,
       now() - v.age
from (values
  ('hist-lead-001','רועי דהן','+97250100001','hist001@example.com','landing_form',null,null,null,'אירוע חברה',62,48,null,null,'won',null,true,interval '641 days 0 hours'),
  ('hist-lead-002','מיכל רוזן','+97250100002',null,'abandoned_order',null,null,null,'אירוע חברה',3,73,700800,null,'lost','המחיר גבוה מהתקציב',false,interval '369 days 3 hours'),
  ('hist-lead-003','שירה מזרחי','+97250100003','hist003@example.com','ai_chat',null,null,null,'יום הולדת',6,50,null,null,'lost','בחרו קייטרינג אחר',true,interval '395 days 18 hours'),
  ('hist-lead-004','מיכל שמש','+97250100004','hist004@example.com','abandoned_order',null,null,null,'אירוע חברה',44,30,493200,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '724 days 20 hours'),
  ('hist-lead-005','תמר מזרחי','+97250100005',null,'landing_form','google','cpc','birthday-fall','אירוע חברה',96,54,965500,null,'won',null,true,interval '348 days 12 hours'),
  ('hist-lead-006','יעל רוזן','+97250100006','hist006@example.com','ai_chat',null,null,null,'יום הולדת',85,32,227500,'יום הולדת בבית, צריך גם מנות לילדים.','lost','המחיר גבוה מהתקציב',false,interval '623 days 13 hours'),
  ('hist-lead-007','מאיה פרידמן','+97250100007',null,'ai_chat',null,null,null,'יום הולדת',7,44,411800,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,false,interval '635 days 14 hours'),
  ('hist-lead-008','גילי אברהם','+97250100008','hist008@example.com','landing_form','facebook','social','spring-offer','בר/בת מצווה',26,127,2311400,'בר מצווה במשפחה, מחפשים תפריט בשרי.','won',null,true,interval '294 days 16 hours'),
  ('hist-lead-009','אורן אזולאי','+97250100009',null,'landing_form','google','organic',null,'בר/בת מצווה',184,117,1186400,null,'lost','המחיר גבוה מהתקציב',false,interval '139 days 11 hours'),
  ('hist-lead-010','תמר אוחיון','+97250100010',null,'ai_chat',null,null,null,'יום הולדת',null,17,104000,null,'lost','המחיר גבוה מהתקציב',true,interval '587 days 5 hours'),
  ('hist-lead-011','עמית אזולאי','+97250100011',null,'whatsapp',null,null,null,'בר/בת מצווה',104,67,1254200,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','האירוע בוטל',false,interval '487 days 3 hours'),
  ('hist-lead-012','שירה ברק','+97250100012',null,'manual',null,null,null,'יום הולדת',13,49,null,null,'won',null,true,interval '710 days 15 hours'),
  ('hist-lead-013','נטע פרץ','+97250100013',null,'ai_chat',null,null,null,'יום הולדת',36,48,null,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','בחרו קייטרינג אחר',false,interval '80 days 21 hours'),
  ('hist-lead-014','איתי ברק','+97250100014','hist014@example.com','ai_chat',null,null,null,'אירוע חברה',38,33,null,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,false,interval '588 days 3 hours'),
  ('hist-lead-015','עידו ברק','+97250100015','hist015@example.com','ai_chat',null,null,null,'בר/בת מצווה',152,148,1558400,null,'lost','המחיר גבוה מהתקציב',true,interval '490 days 9 hours'),
  ('hist-lead-016','איתי אוחיון','+97250100016','hist016@example.com','whatsapp',null,null,null,'אירוע חברה',61,44,459400,null,'won',null,false,interval '568 days 5 hours'),
  ('hist-lead-017','שירה שפירא','+97250100017','hist017@example.com','landing_form','google','organic',null,'יום הולדת',70,27,233300,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','won',null,false,interval '348 days 8 hours'),
  ('hist-lead-018','תמר ביטון','+97250100018',null,'landing_form','google','organic',null,'יום הולדת',null,41,324700,'יום הולדת בבית, צריך גם מנות לילדים.','won',null,false,interval '243 days 16 hours'),
  ('hist-lead-019','תומר פרץ','+97250100019',null,'ai_chat',null,null,null,'בר/בת מצווה',21,87,972700,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '592 days 9 hours'),
  ('hist-lead-020','נטע סגל','+97250100020',null,'ai_chat',null,null,null,'יום הולדת',26,47,313000,null,'lost','המחיר גבוה מהתקציב',false,interval '77 days 2 hours'),
  ('hist-lead-021','איתי חיים','+97250100021','hist021@example.com','landing_form',null,null,null,'בר/בת מצווה',63,56,851800,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','בחרו קייטרינג אחר',true,interval '177 days 17 hours'),
  ('hist-lead-022','דן אברהם','+97250100022',null,'landing_form','instagram','social','stories','יום הולדת',5,14,null,null,'lost','בחרו קייטרינג אחר',false,interval '183 days 7 hours'),
  ('hist-lead-023','עמית דהן','+97250100023','hist023@example.com','abandoned_order',null,null,null,'יום הולדת',111,33,386100,'יום הולדת בבית, צריך גם מנות לילדים.','won',null,false,interval '64 days 15 hours'),
  ('hist-lead-024','ליאת לוי','+97250100024',null,'ai_chat',null,null,null,'יום הולדת',18,26,187200,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','המחיר גבוה מהתקציב',false,interval '720 days 17 hours'),
  ('hist-lead-025','איתי סגל','+97250100025',null,'landing_form','google','organic',null,'בר/בת מצווה',126,73,597900,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','המחיר גבוה מהתקציב',true,interval '219 days 8 hours'),
  ('hist-lead-026','אורן אוחיון','+97250100026',null,'ai_chat',null,null,null,'אירוע חברה',29,107,1605000,'ערב סיום פרויקט, מחפשים משהו קליל.','won',null,false,interval '152 days 23 hours'),
  ('hist-lead-027','אורן דהן','+97250100027',null,'landing_form','google','organic',null,'אירוע חברה',94,90,766800,null,'lost','המחיר גבוה מהתקציב',false,interval '25 days 9 hours'),
  ('hist-lead-028','תומר שמש','+97250100028',null,'manual',null,null,null,'חתונה',55,247,3517300,null,'lost','האירוע בוטל',false,interval '315 days 16 hours'),
  ('hist-lead-029','יעל דהן','+97250100029','hist029@example.com','ai_chat',null,null,null,'יום הולדת',3,27,null,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,false,interval '449 days 20 hours'),
  ('hist-lead-030','איתי ברק','+97250100030',null,'whatsapp',null,null,null,'אירוע חברה',151,51,446800,null,'lost','המחיר גבוה מהתקציב',true,interval '555 days 14 hours'),
  ('hist-lead-031','רועי נחום','+97250100031',null,'ai_chat',null,null,null,'יום הולדת',65,41,265700,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','המחיר גבוה מהתקציב',false,interval '541 days 13 hours'),
  ('hist-lead-032','ליאת שפירא','+97250100032','hist032@example.com','whatsapp',null,null,null,'אירוע חברה',123,53,814100,'כיבוד לכנס של חצי יום.','won',null,false,interval '265 days 8 hours'),
  ('hist-lead-033','נועה אשכנזי','+97250100033','hist033@example.com','landing_form','google','cpc','birthday-fall','יום הולדת',61,21,null,'יום הולדת בבית, צריך גם מנות לילדים.','lost','בחרו קייטרינג אחר',false,interval '623 days 22 hours'),
  ('hist-lead-034','הדס אברהם','+97250100034','hist034@example.com','landing_form','facebook','social','spring-offer','יום הולדת',164,38,369400,'יום הולדת בבית, צריך גם מנות לילדים.','lost','לא ענה לאחר כמה ניסיונות',false,interval '709 days 21 hours'),
  ('hist-lead-035','קרן שפירא','+97250100035',null,'whatsapp',null,null,null,'בר/בת מצווה',null,90,1322100,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,true,interval '360 days 6 hours'),
  ('hist-lead-036','גילי לוי','+97250100036',null,'landing_form','facebook','social','spring-offer','אירוע חברה',null,73,null,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '692 days 1 hours'),
  ('hist-lead-037','אורן פרץ','+97250100037','hist037@example.com','landing_form',null,null,null,'יום הולדת',46,20,null,'רוצה הצעה ליום הולדת עם קינוחים.','lost','בחרו קייטרינג אחר',false,interval '142 days 5 hours'),
  ('hist-lead-038','יוסי אשכנזי','+97250100038',null,'manual',null,null,null,'בר/בת מצווה',null,88,1098200,null,'lost','בחרו קייטרינג אחר',true,interval '725 days 19 hours'),
  ('hist-lead-039','רונית סגל','+97250100039','hist039@example.com','whatsapp',null,null,null,'יום הולדת',null,35,207900,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','המחיר גבוה מהתקציב',false,interval '495 days 22 hours'),
  ('hist-lead-040','קרן אזולאי','+97250100040','hist040@example.com','ai_chat',null,null,null,'אירוע חברה',46,54,745200,null,'won',null,false,interval '113 days 8 hours'),
  ('hist-lead-041','נועה אוחיון','+97250100041',null,'manual',null,null,null,'אירוע חברה',9,105,null,'ארוחת צהריים לצוות, יש כמה צמחונים.','lost','בחרו קייטרינג אחר',false,interval '307 days 17 hours'),
  ('hist-lead-042','יעל חיים','+97250100042','hist042@example.com','whatsapp',null,null,null,'יום הולדת',51,47,541400,null,'won',null,true,interval '338 days 21 hours'),
  ('hist-lead-043','דן דהן','+97250100043','hist043@example.com','whatsapp',null,null,null,'חתונה',44,188,4512000,'חתונה קטנה בגן אירועים, מחפשים תפריט מלא.','won',null,false,interval '573 days 22 hours'),
  ('hist-lead-044','תמר כהן','+97250100044','hist044@example.com','landing_form','google','organic',null,'אירוע חברה',null,117,1502300,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,true,interval '571 days 4 hours'),
  ('hist-lead-045','בני פרץ','+97250100045','hist045@example.com','manual',null,null,null,'אירוע חברה',null,36,505400,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,false,interval '77 days 8 hours'),
  ('hist-lead-046','גילי אוחיון','+97250100046','hist046@example.com','landing_form','google','organic',null,'חתונה',4,93,1101100,'מבקשים הצעה לשולחן קבלת פנים ושולחן מתוקים.','lost','המחיר גבוה מהתקציב',false,interval '658 days 7 hours'),
  ('hist-lead-047','דן אזולאי','+97250100047',null,'whatsapp',null,null,null,'חתונה',77,230,5483200,null,'won',null,true,interval '701 days 2 hours'),
  ('hist-lead-048','נטע אשכנזי','+97250100048','hist048@example.com','landing_form',null,null,null,'יום הולדת',null,40,439200,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,false,interval '264 days 8 hours'),
  ('hist-lead-049','יוסי נחום','+97250100049','hist049@example.com','landing_form',null,null,null,'בר/בת מצווה',4,68,1043100,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','lost','אין זמינות בתאריך',false,interval '320 days 14 hours'),
  ('hist-lead-050','יעל לוי','+97250100050',null,'ai_chat',null,null,null,'אירוע חברה',161,84,1098700,null,'lost','האירוע בוטל',true,interval '715 days 18 hours'),
  ('hist-lead-051','ליאת שפירא','+97250100051',null,'abandoned_order',null,null,null,'אירוע חברה',9,42,514100,null,'won',null,false,interval '381 days 13 hours'),
  ('hist-lead-052','מאיה לוי','+97250100052','hist052@example.com','ai_chat',null,null,null,'אירוע חברה',35,62,721700,null,'won',null,true,interval '143 days 12 hours'),
  ('hist-lead-053','שני מלכה','+97250100053','hist053@example.com','whatsapp',null,null,null,'אירוע חברה',52,72,561600,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,true,interval '319 days 14 hours'),
  ('hist-lead-054','רונית מלכה','+97250100054','hist054@example.com','manual',null,null,null,'יום הולדת',null,27,301300,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,false,interval '145 days 20 hours'),
  ('hist-lead-055','גילי סגל','+97250100055',null,'abandoned_order',null,null,null,'יום הולדת',63,38,461700,'יום הולדת בבית, צריך גם מנות לילדים.','lost','האירוע בוטל',false,interval '96 days 8 hours'),
  ('hist-lead-056','שני אזולאי','+97250100056','hist056@example.com','landing_form',null,null,null,'בר/בת מצווה',42,115,1674400,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,false,interval '354 days 6 hours'),
  ('hist-lead-057','מאיה אשכנזי','+97250100057',null,'abandoned_order',null,null,null,'יום הולדת',32,14,112100,null,'lost','האירוע בוטל',false,interval '62 days 4 hours'),
  ('hist-lead-058','אסף רוזן','+97250100058',null,'ai_chat',null,null,null,'בר/בת מצווה',null,96,861100,'בר מצווה במשפחה, מחפשים תפריט בשרי.','won',null,false,interval '296 days 10 hours'),
  ('hist-lead-059','עמית מזרחי','+97250100059','hist059@example.com','ai_chat',null,null,null,'בר/בת מצווה',160,149,2092000,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,false,interval '725 days 9 hours'),
  ('hist-lead-060','מאיה סגל','+97250100060',null,'abandoned_order',null,null,null,'בר/בת מצווה',166,130,2349100,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','לא ענה לאחר כמה ניסיונות',true,interval '174 days 7 hours'),
  ('hist-lead-061','תומר ברק','+97250100061','hist061@example.com','manual',null,null,null,'יום הולדת',7,36,null,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','won',null,true,interval '501 days 9 hours'),
  ('hist-lead-062','גיא אשכנזי','+97250100062',null,'ai_chat',null,null,null,'יום הולדת',44,49,383700,'יום הולדת בבית, צריך גם מנות לילדים.','won',null,false,interval '415 days 18 hours'),
  ('hist-lead-063','אסף חיים','+97250100063',null,'landing_form','newsletter','email','nov-menu','בר/בת מצווה',124,124,null,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '318 days 7 hours'),
  ('hist-lead-064','גיא ביטון','+97250100064',null,'manual',null,null,null,'אירוע חברה',6,106,1628200,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,true,interval '59 days 18 hours'),
  ('hist-lead-065','אלעד שפירא','+97250100065',null,'landing_form','google','cpc','birthday-fall','בר/בת מצווה',59,65,608400,null,'lost','המחיר גבוה מהתקציב',true,interval '518 days 9 hours'),
  ('hist-lead-066','תמר ברק','+97250100066',null,'whatsapp',null,null,null,'בר/בת מצווה',107,49,465000,null,'lost','המחיר גבוה מהתקציב',false,interval '429 days 0 hours'),
  ('hist-lead-067','נטע מזרחי','+97250100067','hist067@example.com','landing_form','facebook','social','spring-offer','יום הולדת',5,28,284800,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,false,interval '649 days 7 hours'),
  ('hist-lead-068','הדס נחום','+97250100068',null,'ai_chat',null,null,null,'בר/בת מצווה',null,78,null,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','lost','בחרו קייטרינג אחר',true,interval '575 days 4 hours'),
  ('hist-lead-069','יוסי חיים','+97250100069',null,'abandoned_order',null,null,null,'אירוע חברה',179,73,1042400,'כיבוד לכנס של חצי יום.','lost','האירוע בוטל',true,interval '266 days 11 hours'),
  ('hist-lead-070','גילי ברק','+97250100070','hist070@example.com','landing_form','newsletter','email','nov-menu','יום הולדת',191,41,null,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','לא ענה לאחר כמה ניסיונות',false,interval '235 days 2 hours'),
  ('hist-lead-071','נועה חיים','+97250100071','hist071@example.com','landing_form','facebook','social','spring-offer','בר/בת מצווה',7,140,null,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','האירוע בוטל',true,interval '51 days 4 hours'),
  ('hist-lead-072','תומר אוחיון','+97250100072','hist072@example.com','landing_form',null,null,null,'יום הולדת',124,38,365900,null,'lost','האירוע בוטל',false,interval '69 days 23 hours'),
  ('hist-lead-073','רונית פרידמן','+97250100073','hist073@example.com','ai_chat',null,null,null,'חתונה',5,95,2280000,null,'won',null,false,interval '176 days 2 hours'),
  ('hist-lead-074','אלעד דהן','+97250100074','hist074@example.com','manual',null,null,null,'אירוע חברה',44,111,1185500,null,'lost','בחרו קייטרינג אחר',false,interval '691 days 17 hours'),
  ('hist-lead-075','מיכל סגל','+97250100075',null,'landing_form',null,null,null,'חתונה',22,196,3010600,'חתונה קטנה בגן אירועים, מחפשים תפריט מלא.','lost','האירוע בוטל',false,interval '118 days 2 hours'),
  ('hist-lead-076','אסף גולן','+97250100076',null,'manual',null,null,null,'בר/בת מצווה',36,115,2182700,null,'lost','האירוע בוטל',false,interval '77 days 9 hours'),
  ('hist-lead-077','גילי שמש','+97250100077','hist077@example.com','whatsapp',null,null,null,'יום הולדת',null,21,null,null,'lost','בחרו קייטרינג אחר',false,interval '464 days 17 hours'),
  ('hist-lead-078','רונית לוי','+97250100078','hist078@example.com','manual',null,null,null,'אירוע חברה',22,108,null,'ארוחת צהריים לצוות, יש כמה צמחונים.','won',null,false,interval '435 days 2 hours'),
  ('hist-lead-079','מיכל פרידמן','+97250100079',null,'landing_form','google','cpc','birthday-fall','אירוע חברה',180,63,559400,null,'lost','המחיר גבוה מהתקציב',true,interval '75 days 21 hours'),
  ('hist-lead-080','איתי אזולאי','+97250100080','hist080@example.com','whatsapp',null,null,null,'חתונה',5,235,3760000,'מבקשים הצעה לשולחן קבלת פנים ושולחן מתוקים.','won',null,false,interval '708 days 9 hours'),
  ('hist-lead-081','רועי חיים','+97250100081','hist081@example.com','landing_form',null,null,null,'בר/בת מצווה',5,67,1123600,'בר מצווה במשפחה, מחפשים תפריט בשרי.','won',null,true,interval '260 days 16 hours'),
  ('hist-lead-082','דן שמש','+97250100082',null,'abandoned_order',null,null,null,'חתונה',69,191,1894700,null,'lost','המחיר גבוה מהתקציב',false,interval '46 days 10 hours'),
  ('hist-lead-083','מיכל אוחיון','+97250100083','hist083@example.com','manual',null,null,null,'חתונה',72,172,1871400,null,'won',null,false,interval '366 days 5 hours'),
  ('hist-lead-084','גילי מזרחי','+97250100084','hist084@example.com','whatsapp',null,null,null,'אירוע חברה',137,44,749800,null,'won',null,true,interval '641 days 4 hours'),
  ('hist-lead-085','רונית נחום','+97250100085',null,'abandoned_order',null,null,null,'יום הולדת',95,43,394700,null,'lost','בחרו קייטרינג אחר',false,interval '667 days 10 hours'),
  ('hist-lead-086','אסף שמש','+97250100086','hist086@example.com','manual',null,null,null,'חתונה',null,150,2712000,'מבקשים הצעה לשולחן קבלת פנים ושולחן מתוקים.','won',null,false,interval '685 days 2 hours'),
  ('hist-lead-087','מיכל אוחיון','+97250100087','hist087@example.com','manual',null,null,null,'חתונה',23,90,1440000,'חתונה קטנה בגן אירועים, מחפשים תפריט מלא.','won',null,true,interval '376 days 22 hours'),
  ('hist-lead-088','ליאת מזרחי','+97250100088',null,'abandoned_order',null,null,null,'יום הולדת',171,40,385200,'יום הולדת בבית, צריך גם מנות לילדים.','won',null,false,interval '671 days 20 hours'),
  ('hist-lead-089','שני רוזן','+97250100089','hist089@example.com','manual',null,null,null,'יום הולדת',75,30,224100,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','המחיר גבוה מהתקציב',false,interval '342 days 20 hours'),
  ('hist-lead-090','תומר סגל','+97250100090',null,'ai_chat',null,null,null,'אירוע חברה',6,59,778800,null,'lost','האירוע בוטל',false,interval '120 days 20 hours'),
  ('hist-lead-091','תומר שפירא','+97250100091',null,'landing_form','newsletter','email','nov-menu','יום הולדת',6,33,430600,'רוצה הצעה ליום הולדת עם קינוחים.','won',null,true,interval '564 days 1 hours'),
  ('hist-lead-092','עמית גולן','+97250100092',null,'landing_form',null,null,null,'יום הולדת',106,22,null,null,'lost','בחרו קייטרינג אחר',false,interval '264 days 17 hours'),
  ('hist-lead-093','איתי מלכה','+97250100093',null,'landing_form','google','organic',null,'בר/בת מצווה',32,113,2188800,null,'won',null,false,interval '166 days 8 hours'),
  ('hist-lead-094','עמית נחום','+97250100094','hist094@example.com','manual',null,null,null,'בר/בת מצווה',null,53,854400,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,false,interval '472 days 2 hours'),
  ('hist-lead-095','איתי גולן','+97250100095',null,'whatsapp',null,null,null,'בר/בת מצווה',31,90,null,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','lost','לא ענה לאחר כמה ניסיונות',false,interval '174 days 4 hours'),
  ('hist-lead-096','אורן פרץ','+97250100096',null,'whatsapp',null,null,null,'אירוע חברה',142,98,null,null,'won',null,false,interval '320 days 7 hours'),
  ('hist-lead-097','גיא אזולאי','+97250100097','hist097@example.com','whatsapp',null,null,null,'יום הולדת',60,41,243500,null,'won',null,false,interval '26 days 19 hours'),
  ('hist-lead-098','גיא פרידמן','+97250100098','hist098@example.com','landing_form','google','organic',null,'אירוע חברה',54,87,null,null,'won',null,false,interval '675 days 12 hours'),
  ('hist-lead-099','קרן מלכה','+97250100099','hist099@example.com','landing_form',null,null,null,'אירוע חברה',111,50,756000,'כיבוד לכנס של חצי יום.','lost','לא ענה לאחר כמה ניסיונות',false,interval '204 days 21 hours'),
  ('hist-lead-100','איתי דהן','+97250100100','hist100@example.com','landing_form','facebook','social','spring-offer','בר/בת מצווה',159,98,null,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','lost','האירוע בוטל',false,interval '509 days 8 hours'),
  ('hist-lead-101','מאיה פרידמן','+97250100101','hist101@example.com','landing_form','google','organic',null,'בר/בת מצווה',113,74,683000,null,'lost','המחיר גבוה מהתקציב',false,interval '534 days 11 hours'),
  ('hist-lead-102','שני נחום','+97250100102','hist102@example.com','abandoned_order',null,null,null,'בר/בת מצווה',20,50,643500,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','lost','בחרו קייטרינג אחר',true,interval '461 days 5 hours'),
  ('hist-lead-103','נועה ביטון','+97250100103',null,'ai_chat',null,null,null,'יום הולדת',128,34,351900,'רוצה הצעה ליום הולדת עם קינוחים.','lost','בחרו קייטרינג אחר',false,interval '720 days 5 hours'),
  ('hist-lead-104','רונית אוחיון','+97250100104','hist104@example.com','landing_form','facebook','social','spring-offer','יום הולדת',null,35,293000,'יום הולדת בבית, צריך גם מנות לילדים.','lost','בחרו קייטרינג אחר',false,interval '103 days 18 hours'),
  ('hist-lead-105','בני דהן','+97250100105','hist105@example.com','landing_form','newsletter','email','nov-menu','יום הולדת',66,13,147400,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','לא ענה לאחר כמה ניסיונות',false,interval '317 days 22 hours'),
  ('hist-lead-106','שני אברהם','+97250100106','hist106@example.com','whatsapp',null,null,null,'בר/בת מצווה',145,131,null,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,true,interval '332 days 5 hours'),
  ('hist-lead-107','הדס מלכה','+97250100107',null,'landing_form',null,null,null,'אירוע חברה',68,37,359600,'כיבוד לכנס של חצי יום.','lost','המחיר גבוה מהתקציב',true,interval '92 days 9 hours'),
  ('hist-lead-108','דן ביטון','+97250100108','hist108@example.com','whatsapp',null,null,null,'חתונה',43,227,2433400,null,'lost','המחיר גבוה מהתקציב',false,interval '680 days 18 hours'),
  ('hist-lead-109','תמר דהן','+97250100109','hist109@example.com','ai_chat',null,null,null,'חתונה',8,94,2030400,null,'lost','האירוע בוטל',false,interval '315 days 2 hours'),
  ('hist-lead-110','מיכל כהן','+97250100110',null,'landing_form','google','cpc','birthday-fall','יום הולדת',8,44,467300,null,'lost','האירוע בוטל',false,interval '67 days 0 hours'),
  ('hist-lead-111','קרן מזרחי','+97250100111','hist111@example.com','abandoned_order',null,null,null,'אירוע חברה',62,73,null,null,'lost','בחרו קייטרינג אחר',true,interval '440 days 9 hours'),
  ('hist-lead-112','רועי פרץ','+97250100112',null,'whatsapp',null,null,null,'יום הולדת',106,41,287800,null,'won',null,false,interval '404 days 16 hours'),
  ('hist-lead-113','יעל שפירא','+97250100113',null,'whatsapp',null,null,null,'יום הולדת',null,29,null,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '188 days 10 hours'),
  ('hist-lead-114','אורן מלכה','+97250100114','hist114@example.com','whatsapp',null,null,null,'אירוע חברה',4,85,1040400,'כיבוד לכנס של חצי יום.','lost','אין זמינות בתאריך',true,interval '74 days 1 hours'),
  ('hist-lead-115','איתי אשכנזי','+97250100115','hist115@example.com','manual',null,null,null,'בר/בת מצווה',null,100,null,'בר מצווה במשפחה, מחפשים תפריט בשרי.','won',null,false,interval '71 days 12 hours'),
  ('hist-lead-116','גיא ביטון','+97250100116',null,'landing_form','google','cpc','birthday-fall','חתונה',95,195,4024800,'חתונה קטנה בגן אירועים, מחפשים תפריט מלא.','lost','בחרו קייטרינג אחר',false,interval '372 days 17 hours'),
  ('hist-lead-117','אלעד גולן','+97250100117','hist117@example.com','landing_form',null,null,null,'אירוע חברה',null,62,982100,null,'won',null,false,interval '427 days 19 hours'),
  ('hist-lead-118','נועה שמש','+97250100118',null,'whatsapp',null,null,null,'אירוע חברה',136,85,1101600,'ערב סיום פרויקט, מחפשים משהו קליל.','won',null,false,interval '729 days 20 hours'),
  ('hist-lead-119','איתי אשכנזי','+97250100119',null,'manual',null,null,null,'יום הולדת',8,49,493900,null,'won',null,false,interval '722 days 7 hours'),
  ('hist-lead-120','שירה ברק','+97250100120','hist120@example.com','landing_form',null,null,null,'בר/בת מצווה',53,80,1019200,null,'lost','האירוע בוטל',false,interval '166 days 16 hours'),
  ('hist-lead-121','בני דהן','+97250100121',null,'whatsapp',null,null,null,'בר/בת מצווה',26,88,null,'בר מצווה במשפחה, מחפשים תפריט בשרי.','lost','האירוע בוטל',false,interval '295 days 19 hours'),
  ('hist-lead-122','יעל ברק','+97250100122','hist122@example.com','landing_form','newsletter','email','nov-menu','אירוע חברה',50,58,897800,'ערב סיום פרויקט, מחפשים משהו קליל.','won',null,false,interval '319 days 3 hours'),
  ('hist-lead-123','תמר ברק','+97250100123','hist123@example.com','landing_form',null,null,null,'בר/בת מצווה',104,138,2368100,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,true,interval '231 days 17 hours'),
  ('hist-lead-124','נועה ברק','+97250100124','hist124@example.com','manual',null,null,null,'יום הולדת',13,49,null,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','won',null,false,interval '722 days 4 hours'),
  ('hist-lead-125','אלעד כהן','+97250100125',null,'ai_chat',null,null,null,'חתונה',23,201,null,null,'lost','לא ענה לאחר כמה ניסיונות',true,interval '572 days 23 hours'),
  ('hist-lead-126','יוסי שפירא','+97250100126',null,'ai_chat',null,null,null,'חתונה',178,89,2136000,null,'won',null,false,interval '606 days 19 hours'),
  ('hist-lead-127','תמר אברהם','+97250100127','hist127@example.com','ai_chat',null,null,null,'יום הולדת',null,46,443000,null,'lost','בחרו קייטרינג אחר',false,interval '494 days 20 hours'),
  ('hist-lead-128','רונית מלכה','+97250100128','hist128@example.com','abandoned_order',null,null,null,'אירוע חברה',84,92,null,'ערב סיום פרויקט, מחפשים משהו קליל.','lost','לא ענה לאחר כמה ניסיונות',false,interval '122 days 5 hours'),
  ('hist-lead-129','הדס אוחיון','+97250100129',null,'landing_form','google','cpc','birthday-fall','יום הולדת',3,29,381100,null,'won',null,true,interval '339 days 5 hours'),
  ('hist-lead-130','עידו ברק','+97250100130','hist130@example.com','ai_chat',null,null,null,'בר/בת מצווה',20,138,null,null,'won',null,true,interval '645 days 11 hours'),
  ('hist-lead-131','יוסי כהן','+97250100131','hist131@example.com','abandoned_order',null,null,null,'בר/בת מצווה',116,142,null,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '104 days 18 hours'),
  ('hist-lead-132','יעל כהן','+97250100132','hist132@example.com','landing_form',null,null,null,'אירוע חברה',50,86,1032000,null,'won',null,true,interval '450 days 14 hours'),
  ('hist-lead-133','בני כהן','+97250100133','hist133@example.com','manual',null,null,null,'אירוע חברה',114,59,885000,null,'won',null,false,interval '86 days 2 hours'),
  ('hist-lead-134','גיא פרץ','+97250100134','hist134@example.com','landing_form',null,null,null,'יום הולדת',171,38,321500,'מחפשים קייטרינג ליום הולדת, בעיקר סלטים ועיקריות.','lost','בחרו קייטרינג אחר',false,interval '161 days 20 hours'),
  ('hist-lead-135','רונית פרידמן','+97250100135','hist135@example.com','abandoned_order',null,null,null,'אירוע חברה',45,48,777600,null,'won',null,false,interval '496 days 11 hours'),
  ('hist-lead-136','תומר כהן','+97250100136','hist136@example.com','ai_chat',null,null,null,'יום הולדת',178,19,107700,null,'lost','המחיר גבוה מהתקציב',true,interval '482 days 19 hours'),
  ('hist-lead-137','אסף שפירא','+97250100137','hist137@example.com','landing_form','google','cpc','birthday-fall','יום הולדת',null,46,331200,null,'lost','המחיר גבוה מהתקציב',false,interval '351 days 18 hours'),
  ('hist-lead-138','בני כהן','+97250100138',null,'ai_chat',null,null,null,'יום הולדת',null,45,324000,null,'lost','המחיר גבוה מהתקציב',false,interval '462 days 17 hours'),
  ('hist-lead-139','שני ביטון','+97250100139','hist139@example.com','ai_chat',null,null,null,'בר/בת מצווה',36,125,1527500,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,false,interval '255 days 9 hours'),
  ('hist-lead-140','תמר רוזן','+97250100140',null,'manual',null,null,null,'בר/בת מצווה',11,93,null,null,'won',null,false,interval '220 days 1 hours'),
  ('hist-lead-141','שירה פרץ','+97250100141',null,'manual',null,null,null,'אירוע חברה',65,29,268000,'כיבוד לכנס של חצי יום.','lost','המחיר גבוה מהתקציב',false,interval '40 days 6 hours'),
  ('hist-lead-142','גיא אוחיון','+97250100142','hist142@example.com','whatsapp',null,null,null,'בר/בת מצווה',14,71,1135300,'בת מצווה, כ-80 איש, רוצים הצעה מסודרת.','won',null,false,interval '340 days 8 hours'),
  ('hist-lead-143','יעל סגל','+97250100143',null,'ai_chat',null,null,null,'חתונה',22,200,4128000,'מבקשים הצעה לשולחן קבלת פנים ושולחן מתוקים.','won',null,false,interval '591 days 18 hours'),
  ('hist-lead-144','גיא אברהם','+97250100144',null,'landing_form','google','cpc','birthday-fall','יום הולדת',16,27,255200,null,'lost','לא ענה לאחר כמה ניסיונות',false,interval '197 days 23 hours'),
  ('hist-lead-145','עמית מזרחי','+97250100145',null,'whatsapp',null,null,null,'אירוע חברה',143,89,1591300,'כיבוד לכנס של חצי יום.','won',null,true,interval '165 days 20 hours'),
  ('hist-lead-146','תמר ברק','+97250100146','hist146@example.com','landing_form','google','cpc','birthday-fall','יום הולדת',49,15,156600,'יום הולדת בבית, צריך גם מנות לילדים.','won',null,false,interval '567 days 23 hours'),
  ('hist-lead-147','הדס מזרחי','+97250100147','hist147@example.com','ai_chat',null,null,null,'יום הולדת',null,39,466800,'יום הולדת בבית, צריך גם מנות לילדים.','lost','בחרו קייטרינג אחר',true,interval '387 days 8 hours'),
  ('hist-lead-148','נועה אברהם','+97250100148','hist148@example.com','landing_form','google','organic',null,'חתונה',150,156,3045100,null,'lost','בחרו קייטרינג אחר',false,interval '82 days 20 hours'),
  ('hist-lead-149','תמר כהן','+97250100149','hist149@example.com','whatsapp',null,null,null,'חתונה',null,164,2912600,null,'lost','בחרו קייטרינג אחר',true,interval '605 days 15 hours'),
  ('hist-lead-150','דן אשכנזי','+97250100150',null,'landing_form','google','cpc','birthday-fall','אירוע חברה',187,104,786200,null,'lost','המחיר גבוה מהתקציב',false,interval '103 days 9 hours')
) as v(id, full_name, phone, email, source, utm_source, utm_medium, utm_campaign, event_type,
       lead_days, guests, budget, message, status, lost_reason, consent, age);
-- END HISTORY

-- Activity log. Every lead gets a "created" event; later steps are added for the statuses it passed through.
-- Step times are offsets from creation, capped at now() so no event is in the future.
insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'created', null, 'new',
       case source when 'manual' then 'owner' when 'whatsapp' then 'owner' when 'abandoned_order' then 'system' else 'customer' end,
       null, created_at
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%');

insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'status_changed', 'new', 'contacted', 'owner', 'שיחת טלפון ראשונה', least(now(), created_at + interval '3 hours')
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%') and status in ('contacted', 'quoted', 'won', 'lost');

insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'status_changed', 'contacted', 'quoted', 'owner', 'נשלחה הצעת מחיר', least(now(), created_at + interval '1 day')
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%') and status in ('quoted', 'won');

insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'status_changed', 'quoted', 'won', 'owner', 'הלקוח אישר', least(now(), created_at + interval '4 days')
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%') and status = 'won';

insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'converted', null, null, 'system', 'הליד הומר ללקוח והזמנה', least(now(), created_at + interval '4 days' + interval '1 minute')
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%') and customer_id is not null;

insert into public.lead_events (lead_id, type, from_status, to_status, actor, note, created_at)
select id, 'status_changed', 'contacted', 'lost', 'owner', lost_reason, least(now(), created_at + interval '5 days')
from public.leads where (id like 'demo-lead-%' or id like 'hist-lead-%') and status = 'lost';

-- A few free-text notes.
insert into public.lead_events (lead_id, type, actor, note, created_at)
select id, 'note', 'owner', 'ביקש לחזור אליו אחרי הצהריים', least(now(), created_at + interval '1 hour')
from public.leads where id in ('demo-lead-06', 'demo-lead-09', 'demo-lead-10');

-- updated_at = time of the latest event.
update public.leads l
set updated_at = coalesce((select max(e.created_at) from public.lead_events e where e.lead_id = l.id), l.created_at)
where l.id like 'demo-lead-%' or l.id like 'hist-lead-%';

commit;
