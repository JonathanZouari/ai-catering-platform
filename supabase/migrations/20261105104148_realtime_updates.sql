-- Realtime: push row changes to subscribed clients. Realtime applies RLS per subscriber:
-- anonymous visitors only receive rows their SELECT policy allows (menu tables); admins also receive orders.
-- REPLICA IDENTITY FULL makes UPDATE events carry the old row, so the dashboard can show what changed.

alter table public.orders              replica identity full;
alter table public.ai_proposals        replica identity full;
alter table public.dishes              replica identity full;

alter publication supabase_realtime add table
  public.orders,
  public.order_items,
  public.order_status_events,
  public.ai_proposals,
  public.dishes;
