-- Synthetic leads for the dev project. All people, phones and emails are invented.
-- Requires supabase/seed.sql (customers) and the demo owner from backend/scripts/create_demo_users.py.
-- Load with: supabase db query --linked -f supabase/seed_leads.sql
--
-- Covers: every source and status, minimal (name + phone only) and fully filled leads, a landline,
-- a duplicate phone, leads linked to existing customers, past event dates on closed leads, a long message.

do $$
begin
  if exists (select 1 from public.leads) then
    raise exception 'leads seed already loaded: public.leads is not empty';
  end if;
  if not exists (select 1 from public.customers where email = 'demo@example.com') then
    raise exception 'load supabase/seed.sql first';
  end if;
  if not exists (select 1 from auth.users where email = 'owner@example.com') then
    raise exception 'run backend/scripts/create_demo_users.py first';
  end if;
end $$;

do $$
declare
  r record;
  n record;
  v_owner uuid;
  v_lead uuid;
  v_created timestamptz;
  v_last timestamptz;
begin
  select id into v_owner from auth.users where email = 'owner@example.com';

  -- hours_ago: when the lead arrived. days: event date relative to today (negative = already passed).
  -- notes: [[text, hours after the lead arrived], ...]
  for r in select * from (values
    ('רונית שלום', '+972500000101', 'ronit.shalom@example.com', 'בר או בת מצווה', 45, 120,
     'מחפשים קייטרינג לבת מצווה בגן אירועים קטן. חשוב לנו מבחר צמחוני.',
     'landing_form', 'new', null, null, 2, '[]'::jsonb),
    ('אבי כהן', '+972500000102', null, 'ברית', 12, 60,
     'ברית בעוד כשבועיים, נשמח לשיחה.',
     'landing_form', 'new', null, null, 36, '[]'::jsonb),
    ('אבי כהן', '+972500000102', null, 'ברית', 12, 60,
     'שלחתי פנייה גם אתמול, אשמח שיחזרו אליי.',
     'landing_form', 'new', null, null, 1, '[]'::jsonb),
    ('שירה גולן', '+972500000103', 'shira.golan@example.com', 'יום הולדת', 20, 25, null,
     'landing_form', 'new', null, null, 20, '[]'::jsonb),
    ('לקוח דמו', '+972500000000', 'demo@example.com', 'אירוע משפחתי', 35, 40,
     'ביקש שיחה דרך העוזר: שאלות על מנות ללא גלוטן לאירוע של 40 איש.',
     'ai_chat', 'new', null, 'demo@example.com', 48, '[]'::jsonb),
    ('משה ביטון', '+972500000105', null, null, null, null, null,
     'manual', 'new', null, null, 5,
     '[["התקשר לעסק, ביקש שנחזור אליו מחר בבוקר.", 0]]'::jsonb),
    ('קובי אלון', '+972500000118', null, 'בר או בת מצווה', 90, 100,
     'פנה בוואטסאפ, ביקש הצעת מחיר ראשונית.',
     'manual', 'new', null, null, 30, '[]'::jsonb),
    ('תמר אברהם', '+972500000005', 'tamar.avraham@example.com', 'יום נישואין', 50, 20,
     'רוצה לשאול על מנות דגים לאירוע נוסף.',
     'ai_chat', 'new', null, 'tamar.avraham@example.com', 8, '[]'::jsonb),
    ('מיכל ברק', '+972500000114', 'michal.barak@example.com', 'אירוע משפחתי', 60, 80,
     'שלום, אנחנו מתכננים מפגש משפחתי גדול לכבוד יום ההולדת השמונים של סבתא. האירוע יתקיים בחצר הבית, '
     || 'ויהיו בערך שמונים אורחים, מתוכם כעשרים ילדים. יש במשפחה כמה צמחונים ושתי טבעוניות, ואחד הנכדים '
     || 'אלרגי לשומשום, אז חשוב לנו לדעת בדיוק אילו מנות מכילות אותו. אנחנו מעדיפים משלוח עד הבית בשעות '
     || 'הצהריים, ונשמח להבין אם אפשר לחלק את המשלוח לשני מועדים: מנות ראשונות בצהריים וקינוחים לקראת ערב. '
     || 'בנוסף, נשמח לקבל המלצה על כמויות כי זו הפעם הראשונה שאנחנו מזמינים קייטרינג לאירוע בגודל כזה. '
     || 'אפשר לחזור אלינו בכל יום אחרי ארבע. תודה רבה!',
     'landing_form', 'new', null, null, 14, '[]'::jsonb),
    ('הילה אזולאי', '+972500000106', 'hila.azulay@example.com', 'ארוחת שבת', 6, 14,
     'ארוחת שבת לכל המשפחה, שני ילדים עם אלרגיה לאגוזים.',
     'landing_form', 'contacted', null, null, 72,
     '[["שוחחנו בטלפון. שלחתי קישור לבניית הזמנה והסברתי על סימון האלרגנים.", 20]]'::jsonb),
    ('עומר דהן', '+972500000107', 'omer.dahan@example.com', 'יום נישואין', 28, 30,
     'רוצה להפתיע את בת הזוג, מסיבה קטנה בבית.',
     'ai_chat', 'contacted', null, null, 96,
     '[["לא ענה, השארתי הודעה.", 3], ["חזר אליי. מעדיף איסוף עצמי, ישלח הזמנה עד סוף השבוע.", 27]]'::jsonb),
    ('אליהו חדד', '+97239000115', null, 'ארוחת שבת', 13, 18, null,
     'manual', 'contacted', null, null, 120,
     '[["התקשר מהטלפון הקווי בבית. מבקש תפריט פרווה בלבד.", 0], ["שלחתי פירוט מנות פרווה במייל של בתו.", 24]]'::jsonb),
    ('סיון מלכה', '+972500000117', 'sivan.malka@example.com', 'יום הולדת', 8, 35, null,
     'landing_form', 'contacted', null, null, 110,
     '[["שיחה קצרה, ביקשה שנחזור אחרי שתסגור מקום.", 30]]'::jsonb),
    ('נועה לוי', '+972500000001', 'noa.levi@example.com', 'בר או בת מצווה', 21, 75,
     'מעוניינת בתפריט בשרי לבת מצווה.',
     'landing_form', 'converted', null, 'noa.levi@example.com', 288,
     '[["שיחת היכרות, מעוניינת בתפריט בשרי.", 4], ["הגישה הזמנה דרך האפליקציה.", 50]]'::jsonb),
    ('דן כהן', '+972500000002', 'dan.cohen@example.com', 'יום הולדת', 14, 22, null,
     'ai_chat', 'converted', null, 'dan.cohen@example.com', 216,
     '[["הסביר שמעדיף איסוף עצמי. הגיש הזמנה באותו יום.", 6]]'::jsonb),
    ('אורית שמעוני', '+972500000120', null, 'ברית', -5, 45, null,
     'landing_form', 'converted', null, null, 720,
     '[["סגרנו בטלפון, ההזמנה הוזנה ידנית.", 10]]'::jsonb),
    ('גלית אוחיון', '+972500000110', 'galit.ohayon@example.com', 'אירוע משפחתי', -3, 200,
     'אירוע גדול באולם.',
     'landing_form', 'lost', 'מעבר לקיבולת: 200 אורחים', null, 400,
     '[["הסברתי שכרגע אנחנו לא מתאימים לאירועים בגודל כזה.", 5]]'::jsonb),
    ('יעל פרידמן', '+972500000111', 'yael.friedman@example.com', 'ברית', -10, 40, null,
     'landing_form', 'lost', 'בחרו ספק אחר', null, 500,
     '[["שלחתי פרטים, לא חזרה.", 24], ["עדכנה שבחרו ספק אחר.", 96]]'::jsonb),
    ('רועי שפירא', '+972500000112', null, 'יום הולדת', 4, 30, null,
     'landing_form', 'lost', 'לא ניתן ליצור קשר אחרי שלושה ניסיונות', null, 600,
     '[["אין מענה.", 2], ["אין מענה, השארתי הודעה.", 26], ["אין מענה. סוגר.", 75]]'::jsonb),
    ('ליאור נחום', '+972500000119', 'lior.nahum@example.com', 'יום הולדת', -20, 15, null,
     'ai_chat', 'lost', 'מעל התקציב', null, 960,
     '[["שלחתי הערכת מחיר, אמר שזה מעל התקציב.", 12]]'::jsonb)
  ) as t (full_name, phone, email, event_type, days, guests, message, source, status, lost_reason,
          customer_email, hours_ago, notes)
  loop
    v_created := now() - make_interval(hours => r.hours_ago);
    -- Last activity = the latest note, so the list's "updated" column tells a believable story.
    select v_created + make_interval(hours => coalesce(max((value ->> 1)::int), 0)) into v_last
    from jsonb_array_elements(r.notes);

    insert into public.leads (full_name, phone, email, event_type, event_date, guest_count, message,
                              source, status, lost_reason, customer_id, consent_at, created_at, updated_at)
    values (r.full_name, r.phone, r.email, r.event_type, current_date + r.days, r.guests, r.message,
            r.source::public.lead_source, r.status::public.lead_status, r.lost_reason,
            (select id from public.customers where email = r.customer_email),
            case when r.source <> 'manual' then v_created end, v_created, v_last)
    returning id into v_lead;

    for n in select value ->> 0 as body, (value ->> 1)::int as after_hours
             from jsonb_array_elements(r.notes) loop
      insert into public.lead_notes (lead_id, author_id, body, created_at)
      values (v_lead, v_owner, n.body, v_created + make_interval(hours => n.after_hours));
    end loop;
  end loop;
end $$;
