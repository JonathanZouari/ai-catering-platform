"""What Postgres gave for free and SQLite doesn't: locks, exact money, time zones, type checks."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session
from test_orders import Shop

from app.core.db import MIGRATIONS_DIR, apply_migrations, build_engine, read_only
from app.core.email import get_mailer
from app.main import app
from app.models import Dish, DishCategory, Order


@pytest.fixture
def shop(client, make_tenant):
    return Shop(client, make_tenant("caterer-a"))


def test_other_databases_are_refused():
    with pytest.raises(RuntimeError, match="SQLite"):
        build_engine("postgresql://user:secret@host/db")


def test_two_customers_can_not_take_the_last_place(shop):
    shop.patch(f"time-slots/{shop.slot['id']}", {"capacity": 1})
    orders = [shop.order() for _ in range(6)]
    for order in orders:
        order.add(shop.meat)

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(lambda order: order.submit(), orders))

    codes = sorted(response.status_code for response in responses)
    assert codes == [200, 409, 409, 409, 409, 409]


def test_concurrent_edits_of_one_order_can_not_both_win(shop):
    order = shop.order()
    url = f"{order.url}/items/{shop.meat['id']}"
    body = {"quantity": "2", "version": order.data["version"]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(
            pool.map(lambda _: order.client.put(url, json=body, headers=order.headers), range(6))
        )

    assert sorted(response.status_code for response in responses) == [200, 409, 409, 409, 409, 409]


def test_readers_do_not_wait_for_a_writer(engine):
    with engine.begin() as writer:
        writer.execute(text("select 1"))
        with Session(read_only(engine)) as reader:
            assert reader.scalar(text("select count(*) from allergens")) == 13


def test_the_email_is_sent_without_holding_the_write_lock(shop, engine):
    class ProbeMailer:
        lock_was_free = False

        def send(self, to, subject, body):
            probe = sqlite3.connect(engine.url.database, timeout=0)
            probe.execute("begin immediate")
            probe.rollback()
            probe.close()
            ProbeMailer.lock_was_free = True

    shop.patch("profile", {"notification_email": "a@example.com"})
    app.dependency_overrides[get_mailer] = ProbeMailer
    order = shop.order()
    order.add(shop.meat)

    assert order.submit().status_code == 200
    assert ProbeMailer.lock_was_free


def test_uploads_run_without_holding_the_write_lock(shop, engine, storage):
    def upload(path, content, content_type):
        probe = sqlite3.connect(engine.url.database, timeout=0)
        probe.execute("begin immediate")
        probe.rollback()
        probe.close()
        storage.uploads[path] = (content, content_type)

    storage.upload = upload
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    url = f"/api/admin/dishes/{shop.meat['id']}/image"
    files = {"file": ("a.png", png, "image/png")}

    response = shop.client.post(url, files=files, headers=shop.headers)

    assert response.status_code == 200
    assert len(storage.uploads) == 1


def test_money_is_exact_where_a_float_would_drift(shop, session):
    dish = shop.dish("מנה", "0.07", "meat")
    order = shop.order()

    line = order.add(dish, quantity="3")["lines"][-1]

    assert line["unit_price"] == "0.07"
    assert line["line_total"] == "0.21"
    raw = session.scalar(text("select unit_price from dishes where name = 'מנה'"))
    assert raw == 7


def test_an_amount_past_ten_digits_is_refused(session, make_tenant):
    tenant = make_tenant("caterer-a")
    category = DishCategory(caterer_id=tenant.id, name="x")
    session.add(category)
    session.flush()
    session.add(
        Dish(
            caterer_id=tenant.id,
            category_id=category.id,
            name="יקר",
            pricing_unit="per_item",
            unit_price=Decimal("100000000.00"),
        )
    )
    with pytest.raises(StatementError):
        session.flush()
    session.rollback()


def test_times_come_back_in_utc(shop, session):
    order = shop.order()
    israel = timezone(timedelta(hours=3))
    moment = datetime(2031, 6, 1, 12, 0, tzinfo=israel)

    order_id = UUID(order.data["id"])
    stored = session.scalar(select(Order).where(Order.id == order_id))
    stored.submitted_at = moment
    session.commit()
    session.expire_all()

    value = session.scalar(select(Order.submitted_at).where(Order.id == order_id))
    assert value == moment
    assert value.tzinfo == UTC


def test_a_generated_timestamp_reads_back_as_an_aware_time(session, make_tenant):
    tenant = make_tenant("caterer-a")
    session.execute(
        text("insert into dish_categories (caterer_id, name) values (:c, 'x')"), {"c": tenant.id}
    )
    raw = session.scalar(text("select created_at from dish_categories"))
    session.rollback()
    assert datetime.strptime(raw, "%Y-%m-%d %H:%M:%S.%f")


@pytest.mark.parametrize(
    "statement",
    [
        "update caterers set slug = 'Not Valid'",
        "update caterers set slug = '-edge'",
        "update caterers set brand_color = 'red'",
        "update caterers set kashrut_mixing_rule = 'maybe'",
        "update caterers set is_active = 7",
        "update caterers set ai_monthly_message_limit = 'many'",
    ],
)
def test_the_schema_refuses_bad_values(session, make_tenant, statement):
    make_tenant("caterer-a")
    with pytest.raises(IntegrityError):
        session.execute(text(statement))
    session.rollback()


def test_ids_from_the_database_load_as_uuids(session, make_tenant):
    tenant = make_tenant("caterer-a")
    session.execute(
        text("insert into dish_categories (caterer_id, name) values (:c, 'x')"), {"c": tenant.id}
    )
    session.commit()

    loaded = session.scalar(select(DishCategory.id).where(DishCategory.name == "x"))
    assert isinstance(loaded, UUID)


def test_each_migration_runs_once(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'fresh.db'}")

    first = apply_migrations(engine)
    second = apply_migrations(engine)

    assert first == sorted(path.name for path in MIGRATIONS_DIR.glob("*.sql"))
    assert second == []
    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from allergens")) == 13
    engine.dispose()


def test_a_failed_migration_leaves_nothing_behind(tmp_path, monkeypatch):
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "1_bad.sql").write_text(
        "create table half_done (id integer);\nthis is not sql;", encoding="utf-8"
    )
    monkeypatch.setattr("app.core.db.MIGRATIONS_DIR", directory)
    engine = build_engine(f"sqlite:///{tmp_path / 'fresh.db'}")

    with pytest.raises(sqlite3.Error):
        apply_migrations(engine)

    with engine.connect() as connection:
        assert connection.scalar(text("select count(*) from schema_migrations")) == 0
        tables = connection.scalars(text("select name from sqlite_master")).all()
    assert "half_done" not in tables
    engine.dispose()
