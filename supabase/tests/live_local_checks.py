"""LIVE checks against a disposable LOCAL stack: foundation.sql, then two-session lock races.

Needs psql and a database with both migrations applied, e.g. after `supabase start`:

    python supabase/tests/live_local_checks.py postgresql://postgres:postgres@127.0.0.1:54322/postgres

The races COMMIT fixtures, and ledgers are append-only, so run `supabase db reset` afterwards.
Non-local hosts are refused. Exit 0 means every check ran and passed; exit 2 means nothing ran.
"""

import random
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

TESTS = Path(__file__).resolve().parent
BLOCK_SECONDS = 1.5


def fixtures(base):
    """SQL creating committed fixtures with explicit ids, plus the ids used by the races."""
    ids = {name: base + n for n, name in enumerate(
        ("customer", "address", "event", "order", "receipt", "item", "ingredient", "batch"))}
    sql = """
insert into public.customers(id,full_name,phone) values({customer},'RACE TEST','0500000000');
insert into public.addresses(id,customer_id,street,city) values({address},{customer},'Race 1','Race');
insert into public.events(id,customer_id,event_type,event_date,adults) values({event},{customer},'Race',current_date+20,10);
insert into public.orders(id,customer_id,event_id,status,fulfillment_type,requested_at,delivery_address_id,
  subtotal_minor,delivery_fee_minor,total_minor,submitted_at)
  values({order},{customer},{event},'pending_approval','delivery',now()+interval '20 days',{address},8500,6000,14500,now());
insert into public.payments(id,kind,order_id,currency,amount_minor,method,occurred_at)
  values({receipt},'receipt',{order},'ILS',100,'cash',now());
insert into public.equipment_items(id,name,category) values({item},'RACE ITEM {item}','table');
insert into public.equipment_movements(equipment_item_id,movement_type,quantity) values({item},'purchase',3);
insert into public.ingredients(id,name,base_unit) values({ingredient},'RACE INGREDIENT {ingredient}','g');
insert into public.ingredient_batches(id,ingredient_id,received_on)
  values({batch},{ingredient},current_date-1);
insert into public.ingredient_movements(batch_id,movement_type,quantity) values({batch},'receipt',100);
""".format(**ids)
    return sql, ids


def races(ids):
    refund = ("insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at,"
              "refund_of_payment_id,reason) values('refund',{order},'ILS',60,'cash',now(),{receipt},'race');")
    dispatch = ("insert into public.equipment_movements(equipment_item_id,movement_type,quantity,order_id)"
                " values({item},'dispatch',2,{order});")
    consume = ("insert into public.ingredient_movements(batch_id,movement_type,quantity)"
               " values({batch},'consumption',60);")
    food = ("insert into public.deliveries(order_id,address_id,window_start,window_end)"
            " values({order},{address},now(),now()+interval '1 hour');")
    to_pickup = ("update public.orders set fulfillment_type='pickup',delivery_address_id=null,"
                 "delivery_fee_minor=0,total_minor=8500 where id={order};")
    unit = "update public.ingredients set base_unit='ml' where id={ingredient};"
    receipt = ("insert into public.payments(kind,order_id,currency,amount_minor,method,occurred_at)"
               " values('receipt',{order},'ILS',1,'cash',now());")
    batch = "insert into public.ingredient_batches(ingredient_id,received_on) values({ingredient},current_date);"
    order_doc = (
        "'{{\"full_name\":\"RACE\",\"phone\":\"0500000000\",\"street\":\"\",\"city\":\"\","
        "\"event_type\":\"Race\",\"event_date\":\"2030-01-10\",\"adults\":1,\"children\":0,"
        "\"vegetarian_guests\":0,\"vegan_guests\":0,\"restricted_guests\":0,\"dietary_notes\":\"\","
        "\"fulfillment_type\":\"pickup\",\"requested_at\":\"2030-01-10T07:00:00Z\","
        "\"subtotal_minor\":8500,\"delivery_fee_minor\":0,\"total_minor\":8500,\"items\":[{{"
        "\"dish_id\":\"d1\",\"name\":\"Race\",\"unit\":\"tray\",\"quantity_milli\":1000,"
        "\"unit_price_minor\":8500,\"line_total_minor\":8500}}]}}'::jsonb")
    submit = "select public.customer_order_submit('race-{order}','{{\"a\":1}}'," + order_doc + ");"
    # Blocks on the token lock until the first submit commits, then must see its submission.
    resubmit = ("do $$ begin if (public.customer_order_submit('race-{order}','{{\"a\":2}}'," + order_doc
                + "))->>'outcome' = 'conflict' then raise exception 'token conflict after wait'; "
                "end if; end $$;")
    # (label, first session's statement, second session's statement, second session's expected error)
    # An expected error means it must block until commit, then fail; None means it must not block.
    table = [
        ("refund vs refund", refund, refund, "refunds exceed the original receipt"),
        ("dispatch vs dispatch", dispatch, dispatch, "not enough equipment on hand"),
        ("consumption vs consumption", consume, consume, "not enough of this batch on hand"),
        ("food delivery vs pickup change", food, to_pickup, "food drop-off requires a delivery order"),
        ("first movement vs unit change", consume, unit, "cannot change the unit of recorded stock"),
        ("customer submit vs same token", submit, resubmit, "token conflict after wait"),
        ("food delivery does not block order FK inserts", food, receipt, None),
        ("movement does not block batch FK inserts", consume, batch, None),
    ]
    return [(label, a.format(**ids), b.format(**ids), want) for label, a, b, want in table]


def psql_args(url):
    return ["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", url]


def run_foundation(url):
    result = subprocess.run(psql_args(url) + ["-f", str(TESTS / "foundation.sql")],
                            capture_output=True, text=True, encoding="utf-8")
    passed = result.returncode == 0 and "PASS" in result.stderr
    print(("ok   " if passed else "FAIL ") + "foundation.sql")
    if not passed:
        print(result.stderr[-2000:])
    return passed


def run_race(url, label, first, second, want_error):
    session = subprocess.Popen(psql_args(url), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8")
    session.stdin.write(f"begin;\n{first}\n\\echo READY\n")
    session.stdin.flush()
    while "READY" not in session.stdout.readline():
        if session.poll() is not None:
            print(f"FAIL {label}: first session failed: {session.stderr.read()}")
            return False
    # A short lock_timeout for the must-not-block case turns a wait into a visible failure.
    timeout = "set lock_timeout='60s';" if want_error else f"set lock_timeout='{int(BLOCK_SECONDS * 1000)}ms';"
    other = subprocess.Popen(psql_args(url) + ["-c", timeout, "-c", second], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8")
    time.sleep(BLOCK_SECONDS)
    blocked = other.poll() is None
    if want_error is None:
        _, err = other.communicate()
        ok = other.returncode == 0
        detail = err.strip()
        session.stdin.write("rollback;\n")
    else:
        session.stdin.write("commit;\n")
        session.stdin.flush()
        _, err = other.communicate()
        ok = blocked and other.returncode != 0 and want_error in err
        detail = f"blocked={blocked} rc={other.returncode} {err.strip()}"
    session.stdin.close()
    session.wait()
    print(("ok   " if ok else "FAIL ") + label + ("" if ok else f": {detail}"))
    return ok


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    url = sys.argv[1]
    if urlparse(url).hostname not in ("127.0.0.1", "localhost", "::1"):
        print("NOT RUN: refusing a non-local database.")
        return 2
    if not shutil.which("psql"):
        print("NOT RUN: psql is not installed.")
        return 2
    results = [run_foundation(url)]
    # Each race gets fresh fixtures because the previous one consumed stock or changed the order.
    for index in range(len(races(fixtures(0)[1]))):
        sql, ids = fixtures(random.randrange(10**6, 10**12) * 100)
        subprocess.run(psql_args(url) + ["-q", "-c", f"begin;{sql}commit;"], check=True, capture_output=True)
        results.append(run_race(url, *races(ids)[index]))
    print("LIVE local result:", "PASS" if all(results) else "FAIL", "(run `supabase db reset` now)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
