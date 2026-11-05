-- ADR 0003: status and price changes go through the backend only.
-- Remove the Data API write access that the first migration gave admins on orders and order_status_events.
-- Admins keep read access. Catalog and configuration tables keep admin write policies.

drop policy "admin decide" on public.orders;
drop policy "admin log" on public.order_status_events;

revoke update on public.orders from authenticated;
revoke insert on public.order_status_events from authenticated;
