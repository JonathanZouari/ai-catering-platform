-- Lead priority: which leads are worth calling back first, with the reasons in Hebrew.
-- ponytail: the weights below are engineering placeholders, not business rules. Tune them with the owner
-- (lead time is still OPEN_DECISIONS #5). Kept in one view so changing them is a single migration.

create view lead_priority with (security_invoker = true) as
with facts as (
  select
    l.*,
    l.event_date - (now() at time zone 'Asia/Jerusalem')::date as days_to_event,
    (now() at time zone 'Asia/Jerusalem')::date - (l.created_at at time zone 'Asia/Jerusalem')::date as lead_age_days,
    exists (select 1 from public.customers c
            where regexp_replace(coalesce(c.phone, ''), '\D', '', 'g') = l.phone) as is_customer
  from public.leads l
),
points as (
  select f.*,
    case
      when days_to_event is null then 5
      when days_to_event < 0 then 0
      when days_to_event < 3 then 5
      when days_to_event <= 60 then 35
      when days_to_event <= 180 then 20
      else 10
    end as date_points,
    case
      when guests is null then 5
      when guests < 15 then 5
      when guests < 50 then 15
      when guests < 150 then 25
      else 30
    end as size_points,
    (case when event_type is not null then 5 else 0 end
     + case when email is not null then 5 else 0 end
     + case when message is not null then 5 else 0 end) as detail_points,
    case
      when lead_age_days <= 2 then 15
      when lead_age_days <= 7 then 10
      when lead_age_days <= 30 then 5
      else 0
    end as freshness_points,
    case when is_customer then 10 else 0 end as customer_points
  from facts f
),
scored as (
  select p.*,
    least(100, date_points + size_points + detail_points + freshness_points + customer_points) as score
  from points p
)
select
  id, full_name, phone, email, event_type, event_date, guests, message, status, notes, created_at,
  days_to_event, lead_age_days, is_customer,
  case when status in ('won', 'lost') or days_to_event < 0 then 0 else score end as score,
  case
    when status in ('won', 'lost') then 'closed'
    when days_to_event < 0 then 'skip'
    when score >= 60 then 'today'
    when score >= 35 then 'week'
    else 'low'
  end as tier,
  array_remove(array[
    case when days_to_event < 0 then 'תאריך האירוע כבר עבר' end,
    case when days_to_event between 0 and 2 then 'האירוע בעוד פחות מ-3 ימים, ייתכן שמאוחר מדי' end,
    case when days_to_event between 3 and 60 then 'האירוע בחודשיים הקרובים' end,
    case when days_to_event > 180 then 'האירוע רחוק, אין דחיפות' end,
    case when event_date is null then 'לא צוין תאריך' end,
    case when guests >= 150 then 'אירוע גדול מאוד' when guests >= 50 then 'אירוע גדול' end,
    case when guests < 15 then 'אירוע קטן' end,
    case when guests is null then 'לא צוין מספר אורחים' end,
    case when is_customer then 'לקוח קיים' end,
    case when lead_age_days <= 2 then 'פנייה טרייה' when lead_age_days > 30 then 'פנייה ישנה' end,
    case when detail_points >= 10 then 'השאיר פרטים מלאים' end
  ], null) as reasons
from scored;

-- Views also get Supabase's default grants; only signed-in users may query it, and RLS on leads
-- (security_invoker) limits the rows to the admin.
revoke all on lead_priority from anon, public;
revoke all on lead_priority from authenticated;
grant select on lead_priority to authenticated;
