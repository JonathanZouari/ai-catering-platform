-- Synthetic leads for the dev project. All people and numbers are invented.
-- Dates are relative to the load day, so the mix (hot, cold, expired) stays meaningful.
-- Load after seed.sql:  supabase db query --linked -f supabase/seed_leads.sql
-- Never load in production.

do $$
begin
  if exists (select 1 from public.leads) then
    raise exception 'leads seed already loaded: public.leads is not empty';
  end if;
end $$;

insert into public.leads (full_name, phone, email, event_type, event_date, guests, message, status, notes, created_at)
select full_name, phone, email, event_type, current_date + event_in, guests, message,
       status::public.lead_status, notes, now() - make_interval(days => age_days, hours => age_hours)
from (values
  -- Strong: near event, big, full details, fresh
  ('אורית בן דוד',   '0520000001', 'orit.bd@example.com',     'בר או בת מצווה', 21,   120, 'מחפשים תפריט בשרי מלא, כולל מנות לילדים.', 'new', null, 0, 3),
  ('אלון שגיא',      '0520000002', 'alon.sagi@example.com',   'אירוע משפחתי',   14,   60,  'יום הולדת 70 לאבא, בחצר.', 'new', null, 1, 5),
  ('רונית חדד',      '0520000003', null,                      'חגיגה פרטית',    30,   200, 'אירוע חברה בסוף החודש.', 'new', null, 0, 1),
  ('עידו קפלן',      '0520000004', 'ido.kaplan@example.com',  'יום נישואין',    10,   45,  'עשרים שנה לנישואין, רוצים משהו מיוחד.', 'new', null, 2, 0),
  ('שירה אלמוג',     '0520000005', 'shira.a@example.com',     'בר או בת מצווה', 45,   150, null, 'contacted', 'דיברנו, מחכה לרשימת מוזמנים.', 4, 0),
  -- Existing customers coming back (phones match seed.sql customers)
  ('מאיה פרץ',       '0500000003', 'maya.peretz@example.com', 'ארוחת שבת',      9,    25,  'הזמנו בעבר והיה מצוין.', 'new', null, 1, 2),
  ('תמר אברהם',      '0500000005', null,                      'יום הולדת',      35,   30,  null, 'new', null, 3, 0),
  -- Middle: some details missing, or event further away
  ('גלעד רוזן',      '0520000006', null,                      'יום הולדת',      40,   20,  null, 'new', null, 5, 0),
  ('הדס מימון',      '0520000007', 'hadas.m@example.com',     'אירוע משפחתי',   95,   80,  'ברית בעוד כמה חודשים.', 'new', null, 2, 4),
  ('יעל ברק',        '0520000008', null,                      null,             null, null, 'רציתי לשמוע מחירים.', 'new', null, 0, 6),
  ('אסף נחום',       '0520000009', 'asaf.n@example.com',      'חגיגה פרטית',    150,  70,  null, 'new', null, 6, 0),
  ('ליאת גבאי',      '0520000010', null,                      'ארוחת שבת',      12,   12,  null, 'new', null, 3, 0),
  ('משה אוחיון',     '0520000011', null,                      'אירוע משפחתי',   null, 40,  null, 'new', null, 8, 0),
  ('נטע שלום',       '0520000012', 'neta.s@example.com',      'יום הולדת',      25,   18,  'יום הולדת 40 בהפתעה.', 'quoted', 'נשלחה הצעה ב-1,800 ₪.', 9, 0),
  ('רועי טל',        '0520000013', null,                      'בר או בת מצווה', 240,  180, null, 'new', null, 4, 0),
  -- Weak: tiny, far, vague or old
  ('ענבל דהן',       '0520000014', null,                      null,             300,  8,   null, 'new', null, 20, 0),
  ('אבי סעדה',       '0520000015', null,                      'ארוחת שבת',      null, 6,   null, 'new', null, 35, 0),
  ('דנה וקנין',      '0520000016', null,                      null,             null, null, null, 'new', null, 45, 0),
  ('קובי לוגסי',     '0520000017', null,                      'יום הולדת',      200,  10,  null, 'new', null, 28, 0),
  ('מירב אשכנזי',    '0520000018', null,                      'חגיגה פרטית',    1,    35,  'צריך למחר בערב, אפשרי?', 'new', null, 0, 2),
  -- Expired: the event date is already behind us
  ('שי ביטון',       '0520000019', 'shai.b@example.com',      'יום הולדת',      -5,   50,  null, 'new', null, 25, 0),
  ('אורנה פישר',     '0520000020', null,                      'אירוע משפחתי',   -20,  90,  null, 'contacted', 'לא ענתה פעמיים.', 40, 0),
  -- Closed
  ('יונתן ממן',      '0520000021', 'yonatan.m@example.com',   'בר או בת מצווה', 60,   140, null, 'won', 'נסגר, הוזמן באתר.', 12, 0),
  ('רחל עזרא',       '0520000022', null,                      'ארוחת שבת',      7,    15,  null, 'lost', 'בחרה קייטרינג אחר בגלל מחיר.', 10, 0),
  -- More volume
  ('טל מרקוביץ',     '0520000023', 'tal.m@example.com',       'אירוע משפחתי',   18,   55,  'אזכרה, אוכל חלבי בלבד.', 'new', null, 1, 0),
  ('אביגיל חזן',     '0520000024', null,                      'חגיגה פרטית',    75,   35,  null, 'new', null, 12, 0),
  ('ניר עמר',        '0520000025', 'nir.amar@example.com',    'יום הולדת',      6,    22,  'גן ילדים, 22 ילדים.', 'new', null, 0, 8),
  ('סיגל רביבו',     '0520000026', null,                      null,             50,   null, null, 'new', null, 15, 0),
  ('עומר יוסף',      '0520000027', 'omer.y@example.com',      'בר או בת מצווה', 120,  220, 'אולם בצפון, צריך משלוח.', 'contacted', 'שלחתי תפריט במייל.', 7, 0),
  ('לימור בוזגלו',   '0520000028', null,                      'ארוחת שבת',      4,    10,  null, 'new', null, 60, 0)
) as t (full_name, phone, email, event_type, event_in, guests, message, status, notes, age_days, age_hours);
