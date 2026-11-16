-- Lead priority, second pass after reviewing the synthetic data:
--   * "today" needs 80+ (was 60), "week" needs 50+ (was 35), so "today" is a short list.
--   * Leads already contacted or quoted get their own tier, follow_up, instead of competing with new ones.
--   * An event in under 3 days is urgent: call now or it is lost (lead time is still OPEN_DECISIONS #5).
--   * A lead older than 30 days that nobody handled drops to low.
--   * Every score band now has a reason, so no lead shows an empty explanation.

create or replace view lead_priority with (security_invoker = true) as
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
    when status in ('contacted', 'quoted') then 'follow_up'
    when days_to_event between 0 and 2 then 'today'
    when lead_age_days > 30 then 'low'
    when score >= 80 then 'today'
    when score >= 50 then 'week'
    else 'low'
  end as tier,
  array_remove(array[
    case when days_to_event < 0 then 'תאריך האירוע כבר עבר' end,
    case when days_to_event between 0 and 2 then 'דחוף: האירוע בעוד פחות מ-3 ימים, לבדוק אם אפשר בכלל' end,
    case when days_to_event between 3 and 60 then 'האירוע בחודשיים הקרובים' end,
    case when days_to_event between 61 and 180 then 'האירוע בעוד 2–6 חודשים' end,
    case when days_to_event > 180 then 'האירוע רחוק, אין דחיפות' end,
    case when event_date is null then 'לא צוין תאריך' end,
    case when guests >= 150 then 'אירוע גדול מאוד' when guests >= 50 then 'אירוע גדול'
         when guests >= 15 then 'אירוע בינוני' when guests < 15 then 'אירוע קטן' end,
    case when guests is null then 'לא צוין מספר אורחים' end,
    case when is_customer then 'לקוח קיים' end,
    case when status = 'contacted' then 'כבר נוצר קשר, לעקוב' when status = 'quoted' then 'נשלחה הצעה, לעקוב' end,
    case when lead_age_days <= 2 then 'פנייה טרייה' when lead_age_days > 30 then 'פנייה ישנה' end,
    case when detail_points >= 10 then 'השאיר פרטים מלאים' end
  ], null) as reasons
from scored;
