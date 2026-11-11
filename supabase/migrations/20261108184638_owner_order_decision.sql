-- Owner approve/reject. Called only by the backend, with the server-side secret API key, after the
-- backend has asked Supabase Auth who the bearer token belongs to and found
-- app_metadata.role = 'catering_owner'. The database never sees the owner's token.
--
-- No new columns and no data change: status, version, decided_at and decision_note already exist.
-- SECURITY INVOKER as service_role, which may now update exactly these four order columns and
-- nothing else; prices, items, events and submissions stay insert-only for it. RLS and the owner
-- policies are unchanged. orders_status_transition still refuses every transition other than
-- pending_approval -> approved | rejected, and orders_touch keeps updated_at.
grant update (status, version, decided_at, decision_note) on public.orders to service_role;

-- Returns {"decided": bool, "order": {id, status, version, decision_note, decided_at} | null}.
-- One UPDATE is the compare and the write: a concurrent second call waits for the row lock, then
-- re-checks its WHERE against the committed row and matches nothing, so version moves once.
-- decided = false means the compare failed. The order is then read again (VOLATILE, READ COMMITTED:
-- a fresh snapshot) and the backend tells an identical replay from a conflict by that row, which is
-- safe because approved and rejected are final. A missing order returns order = null.
-- The backend trims the note; an empty note is stored as NULL.
create function public.owner_order_decide(p_order_id bigint, p_decision text,
  p_expected_version bigint, p_note text)
returns jsonb
language plpgsql volatile security invoker set search_path = '' as $fn$
declare
  v_decided boolean;
  v_order jsonb;
begin
  if p_decision is null or p_decision not in ('approved', 'rejected') then
    raise exception 'invalid decision' using errcode = '22023';
  end if;
  if char_length(p_note) > 2000 then
    raise exception 'decision note is too long' using errcode = '22001';
  end if;

  update public.orders o
     set status = p_decision, version = o.version + 1, decided_at = now(),
         decision_note = nullif(p_note, '')
   where o.id = p_order_id and o.status = 'pending_approval' and o.version = p_expected_version;
  v_decided := found;

  select jsonb_build_object(
      'id', o.id, 'status', o.status, 'version', o.version, 'decision_note', o.decision_note,
      'decided_at', to_char(o.decided_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))
    into v_order
  from public.orders o where o.id = p_order_id;

  return jsonb_build_object('decided', v_decided, 'order', v_order);
end; $fn$;

revoke all on function public.owner_order_decide(bigint, text, bigint, text)
  from public, anon, authenticated;
grant execute on function public.owner_order_decide(bigint, text, bigint, text) to service_role;
