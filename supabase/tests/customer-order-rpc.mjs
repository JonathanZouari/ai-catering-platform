// Customer order RPC behaviour on real SQL, in the isolated PGlite from local-postgres.mjs.
// Single connection: concurrent requests require a separate live test.
import assert from 'node:assert/strict';

const TABLES = ['customers', 'addresses', 'events', 'orders', 'order_items', 'order_submissions'];
const RPC_CALLS = [
  'select public.customer_catalog()',
  "select public.customer_order_read('h')",
  "select public.customer_order_submit('h','{}','{}'::jsonb)",
];

const draft = (over = {}) => ({
  full_name: 'בדיקה', phone: '0501234567', street: 'רחוב 1', city: 'תל אביב-יפו',
  event_type: 'יום הולדת', event_date: '2030-01-10', adults: 10, children: 2,
  vegetarian_guests: 1, vegan_guests: 0, restricted_guests: 0, dietary_notes: '',
  fulfillment_type: 'delivery', requested_at: '2030-01-10T07:00:00Z',
  subtotal_minor: 28100, delivery_fee_minor: 6000, total_minor: 34100,
  items: [
    { dish_id: 'd5', name: 'עוף', unit: 'kg', quantity_milli: 1500, unit_price_minor: 7400, line_total_minor: 11100 },
    { dish_id: 'd1', name: 'חומוס', unit: 'tray', quantity_milli: 2000, unit_price_minor: 8500, line_total_minor: 17000 },
  ],
  ...over,
});

export async function checkCustomerOrderRpc(db) {
  const counts = async () => {
    const out = {};
    for (const table of TABLES) {
      out[table] = (await db.query(`select count(*)::int as n from public.${table}`)).rows[0].n;
    }
    return out;
  };
  // Autocommit on purpose: rollback must come from the RPC's own statement, not a test transaction.
  const asService = async (sql, params = []) => {
    await db.exec('set role service_role');
    try { return (await db.query(sql, params)).rows[0]; } finally { await db.exec('reset role'); }
  };
  const submit = async (hash, payload, order) => (await asService(
    'select public.customer_order_submit($1,$2,$3::jsonb) as r', [hash, payload, JSON.stringify(order)])).r;
  const read = async (hash, id = null) => (await asService(
    'select public.customer_order_read($1,$2::bigint) as r', [hash, id])).r;
  const asRole = (role, claims, sql) => db.transaction(async tx => {
    await tx.exec(`set local role ${role}`);
    await tx.query("select set_config('request.jwt.claims',$1,true)", [JSON.stringify(claims)]);
    return tx.exec(sql);
  });
  const staff = { app_metadata: { role: 'catering_owner' } };

  // Capability denial: not even a staff JWT may call the customer RPCs.
  for (const call of RPC_CALLS) {
    await assert.rejects(asRole('anon', {}, call), /permission denied for function/);
    await assert.rejects(asRole('authenticated', staff, call), /permission denied for function/);
  }

  // Explicit grants: exactly what the invoker functions touch, and nothing destructive.
  const privileges = (await db.query(`select
      has_schema_privilege('service_role','public','usage') as schema_usage,
      has_table_privilege('service_role','public.dishes','select') as dishes_read,
      has_table_privilege('service_role','public.orders','select,insert') as orders_write,
      has_table_privilege('service_role','public.order_submissions','select,insert') as submissions_write,
      has_sequence_privilege('service_role','public.orders_id_seq','usage') as order_seq,
      has_sequence_privilege('service_role','public.customers_id_seq','usage') as customer_seq,
      has_sequence_privilege('service_role','public.addresses_id_seq','usage') as address_seq,
      has_sequence_privilege('service_role','public.events_id_seq','usage') as event_seq`)).rows[0];
  assert.ok(Object.values(privileges).every(Boolean), JSON.stringify(privileges));
  const definers = await db.query(`select p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname like 'customer\\_%' and p.prosecdef`);
  assert.equal(definers.rows.length, 0);

  // Catalog: natural dish order, and only the expected fields.
  const { c } = await asService('select public.customer_catalog() as c');
  assert.deepEqual(c.dishes.slice(0, 3).map(d => d.id), ['d1', 'd2', 'd3']);
  assert.equal(c.dishes.length, 17);
  assert.equal(c.dishes[9].id, 'd10');
  assert.deepEqual(Object.keys(c.dishes[0]).sort(), ['id', 'metadata', 'price_minor', 'step_milli']);
  assert.deepEqual(c.zones.map(z => z.fee_minor)[0], 6000);
  assert.equal(c.zones.length, 6);

  const hash = 'a'.repeat(64);
  const before = await counts();
  assert.equal(await read(hash), null);

  // Created: every table together, with the receipt the API shapes.
  const created = await submit(hash, '{"p":1}', draft());
  assert.equal(created.outcome, 'created');
  const added = await counts();
  assert.deepEqual(added, {
    customers: before.customers + 1, addresses: before.addresses + 1, events: before.events + 1,
    orders: before.orders + 1, order_items: before.order_items + 2,
    order_submissions: before.order_submissions + 1,
  });
  const saved = created.saved;
  assert.equal(saved.order.status, 'pending_approval');
  assert.equal(saved.order.version, 1);
  assert.equal(saved.order.total_minor, 34100);
  assert.match(saved.order.submitted_at, /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/);
  assert.deepEqual(saved.items.map(i => i.name), ['חומוס', 'עוף']);

  // Reads: the token owns the order; a wrong id or token finds nothing.
  assert.deepEqual(await read(hash), saved);
  assert.deepEqual(await read(hash, saved.order.id), saved);
  assert.equal(await read(hash, saved.order.id + 1), null);
  assert.equal(await read('b'.repeat(64), saved.order.id), null);

  // Same token: identical payload replays, a different one conflicts, and neither writes.
  const replay = await submit(hash, '{"p":1}', draft());
  assert.equal(replay.outcome, 'existing');
  assert.deepEqual(replay.saved, saved);
  assert.deepEqual(await submit(hash, '{"p":2}', draft()), { outcome: 'conflict' });
  assert.deepEqual(await counts(), added);

  // A status change by staff reaches the customer's next read.
  await db.exec(`update public.orders set status='approved', decided_at=now(), decision_note='מאושר' where id=${saved.order.id}`);
  const decided = await read(hash);
  assert.equal(decided.order.status, 'approved');
  assert.equal(decided.order.decision_note, 'מאושר');

  // Stale quotes write nothing.
  const staleItem = draft({ items: [{ ...draft().items[1], unit_price_minor: 1 }] });
  assert.deepEqual(await submit('c'.repeat(64), '{}', staleItem), { outcome: 'price_changed' });
  const missingDish = draft({ items: [{ ...draft().items[1], dish_id: 'nope' }] });
  assert.deepEqual(await submit('c'.repeat(64), '{}', missingDish), { outcome: 'price_changed' });
  assert.deepEqual(await submit('c'.repeat(64), '{}', draft({ delivery_fee_minor: 1, total_minor: 28101 })), { outcome: 'price_changed' });
  assert.deepEqual(await counts(), added);

  // Pickup creates no address.
  const pickup = await submit('d'.repeat(64), '{}', draft({
    fulfillment_type: 'pickup', street: '', city: '', delivery_fee_minor: 0, total_minor: 28100,
  }));
  assert.equal(pickup.outcome, 'created');
  const afterPickup = await counts();
  assert.equal(afterPickup.addresses, added.addresses);
  assert.equal(afterPickup.orders, added.orders + 1);

  // Atomicity: failures after earlier inserts leave no row anywhere and can be retried.
  await assert.rejects(submit('e'.repeat(64), '{}', draft({ subtotal_minor: 28000, total_minor: 34000 })),
    /do not add up/);
  assert.deepEqual(await counts(), afterPickup);
  await db.exec(`create function public.fail_last_insert() returns trigger language plpgsql
      set search_path='' as $f$ begin raise exception 'injected failure'; end $f$;
    create trigger fail_last_insert before insert on public.order_submissions
      for each row execute function public.fail_last_insert();`);
  await assert.rejects(submit('e'.repeat(64), '{}', draft()), /injected failure/);
  assert.deepEqual(await counts(), afterPickup, 'failure at the last insert must leave nothing');
  await db.exec(`drop trigger fail_last_insert on public.order_submissions;
    drop function public.fail_last_insert();`);
  assert.equal((await submit('e'.repeat(64), '{}', draft())).outcome, 'created');

  // Staff admin keeps reading the same rows through its own policy.
  const seen = await asRole('authenticated', staff,
    `select o.status, i.name from public.orders o join public.order_items i on i.order_id=o.id
     where o.id=${saved.order.id} order by i.dish_id`);
  assert.deepEqual(seen[0].rows.map(r => r.name), ['חומוס', 'עוף']);
  const stranger = await asRole('authenticated', { user_metadata: { role: 'catering_owner' } },
    `select * from public.orders where id=${saved.order.id}`);
  assert.equal(stranger[0].rows.length, 0);

  // The normalized MVP has 17 public application tables.
  const shape = (await db.query(`select
    (select count(*)::int from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='public' and c.relkind='r') as tables,
    (select count(*)::int from pg_constraint c join pg_namespace n on n.oid=c.connamespace
      where n.nspname='public' and c.contype='f') as fks`)).rows[0];
  assert.equal(shape.tables, 17);
  assert.ok(shape.fks >= 17);
}
