-- More fictitious demo data (idempotent by *.demo@example.com).
insert into customers (full_name, email, phone)
select * from (values
  ('רונית שמעוני','ronit.demo@example.com','050-0000004'),
  ('אורי דיין','uri.demo@example.com','050-0000005'),
  ('נועה פרידמן','noa.demo@example.com','050-0000006'),
  ('אבי מזרחי','avi.demo@example.com','050-0000007'),
  ('שירה גולן','shira.demo@example.com','050-0000008')
) v(n,e,p) where not exists (select 1 from customers where email = v.e);

with ev as (
  insert into events (customer_id, event_type, event_date, adults, children, vegetarian_guests, vegan_guests, restricted_guests, dietary_notes)
  select c.id, v.t, current_date + v.d, v.a, v.k, v.vg, v.vn, v.r, v.note
  from customers c join (values
    ('ronit.demo@example.com','אירוע חברה',10,40,0,6,2,1,'ללא גלוטן ל-2 אורחים'),
    ('uri.demo@example.com','יום נישואין',21,10,0,1,0,0,null),
    ('noa.demo@example.com','בת מצווה',45,50,20,5,2,3,'אלרגיה לחלב'),
    ('avi.demo@example.com','מסיבת גן',5,15,10,4,1,0,null),
    ('shira.demo@example.com','ארוחת שישי',3,8,3,2,2,0,null)
  ) v(em,t,d,a,k,vg,vn,r,note) on v.em = c.email
  where not exists (select 1 from events e where e.customer_id = c.id)
  returning id, customer_id
)
insert into orders (customer_id, event_id, status, fulfillment_type, requested_at, delivery_address, delivery_zone_id, submitted_at, decided_at, decision_note)
select ev.customer_id, ev.id, s.st, s.ft, now() + (s.d || ' days')::interval,
  case s.ft when 'delivery' then s.addr end,
  case s.ft when 'delivery' then (select id from delivery_zones where name = s.zone) end,
  case when s.st <> 'draft' then now() - interval '2 days' end,
  case when s.st in ('approved','rejected') then now() - interval '1 day' end,
  case s.st when 'rejected' then 'התאריך תפוס' end
from ev join customers c on c.id = ev.customer_id
join (values
  ('ronit.demo@example.com','pending_approval','delivery',10,'דרך מנחם בגין 10, תל אביב','תל אביב-יפו'),
  ('uri.demo@example.com','approved','pickup',21,null,null),
  ('noa.demo@example.com','pending_approval','delivery',45,'רחוב הרצל 5, הרצליה','הרצליה'),
  ('avi.demo@example.com','rejected','pickup',5,null,null),
  ('shira.demo@example.com','draft','pickup',3,null,null)
) s(em,st,ft,d,addr,zone) on s.em = c.email;

insert into order_items (order_id, dish_id, quantity)
select o.id, d.id, q.qty
from orders o join customers c on c.id = o.customer_id and c.email in
  ('ronit.demo@example.com','uri.demo@example.com','noa.demo@example.com','avi.demo@example.com','shira.demo@example.com')
cross join (values ('סלט קינואה',3),('חזה עוף בתנור',8),('אורז בסמטי',2),('סלט פירות',30)) q(dn,qty)
join dishes d on d.name = q.dn
on conflict do nothing;

-- Snapshots and totals for every submitted demo order (line = quantity * unit_price, agorot).
update order_items oi set snapshot_name = d.name, snapshot_pricing_unit = d.pricing_unit,
  snapshot_unit_price = d.unit_price, snapshot_line_total = round(oi.quantity * d.unit_price)
from dishes d, orders o
where d.id = oi.dish_id and o.id = oi.order_id and o.status <> 'draft' and oi.snapshot_name is null;

update orders o set subtotal = s.sub, delivery_fee = coalesce(z.fee, 0), total = s.sub + coalesce(z.fee, 0)
from (select order_id, sum(snapshot_line_total) sub from order_items group by order_id) s
left join delivery_zones z on true
where s.order_id = o.id and o.status <> 'draft' and o.subtotal is null
  and (z.id = o.delivery_zone_id or (o.delivery_zone_id is null and z.id is null) or z.id is null);

-- One AI conversation with a pending change proposal.
with o as (select o.id, o.version from orders o join customers c on c.id = o.customer_id where c.email = 'ronit.demo@example.com'),
conv as (insert into ai_conversations (order_id) select id from o
  where not exists (select 1 from ai_conversations a where a.order_id = o.id) returning id, order_id),
msg as (insert into ai_messages (conversation_id, role, content) select id, r.role, r.content::jsonb from conv,
  (values ('user','{"text":"אפשר להחליף את העוף בסלמון?"}'),('assistant','{"text":"בטח, הכנתי הצעה להחלפה. אשמח לאישורך."}')) r(role,content))
insert into ai_change_proposals (order_id, conversation_id, base_order_version, changes, price_before, price_after)
select o.id, conv.id, o.version,
  '[{"op":"replace","from":"חזה עוף בתנור","to":"סלמון בגריל"}]'::jsonb, 60000, 90000
from o join conv on conv.order_id = o.id;
