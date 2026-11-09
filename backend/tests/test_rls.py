"""Row-level security, as the Supabase Data API and Realtime apply it.

Each query runs as the "authenticated" or "anon" role with the login's user id in the JWT
claims, the way Supabase runs them. The backend itself connects as a privileged role.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import ProgrammingError
from test_orders import Shop


@contextmanager
def as_user(engine: Engine, user_id: UUID | None) -> Iterator[Connection]:
    with engine.connect() as connection, connection.begin() as transaction:
        connection.execute(text("set local role " + ("authenticated" if user_id else "anon")))
        if user_id:
            connection.execute(
                text("select set_config('request.jwt.claim.sub', :sub, true)"),
                {"sub": str(user_id)},
            )
        yield connection
        transaction.rollback()


def ids(connection: Connection, table: str) -> set:
    return set(connection.scalars(text(f"select caterer_id from {table}")))  # noqa: S608


@pytest.fixture
def two_shops(client, make_tenant):
    a, b = Shop(client, make_tenant("rls-a")), Shop(client, make_tenant("rls-b"))
    for shop in (a, b):
        shop.order().add(shop.meat)
    return a, b


TENANT_TABLES = [
    "caterer_users",
    "customers",
    "events",
    "dish_categories",
    "dishes",
    "time_slots",
    "orders",
    "order_items",
]


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_caterer_reads_only_its_own_rows(engine, two_shops, table):
    a, b = two_shops
    with as_user(engine, a.tenant.user_id) as connection:
        assert ids(connection, table) == {a.tenant.id}
    with as_user(engine, b.tenant.user_id) as connection:
        assert ids(connection, table) == {b.tenant.id}


def test_caterer_sees_only_itself(engine, two_shops):
    a, _ = two_shops
    with as_user(engine, a.tenant.user_id) as connection:
        assert set(connection.scalars(text("select id from caterers"))) == {a.tenant.id}


def test_dish_details_follow_the_dish(engine, two_shops):
    a, _ = two_shops
    own = {a.meat["id"], a.dairy["id"]}
    with as_user(engine, a.tenant.user_id) as connection:
        dishes = set(connection.scalars(text("select dish_id::text from dish_dietary")))
    assert dishes == own


def test_caterer_reads_platform_defaults_and_allergens(engine, two_shops):
    a, _ = two_shops
    with as_user(engine, a.tenant.user_id) as connection:
        assert connection.scalar(text("select count(*) from quantity_rules")) == 6
        assert connection.scalar(text("select count(*) from allergens")) == 13


def test_login_without_a_caterer_sees_nothing(engine, two_shops):
    with as_user(engine, uuid4()) as connection:
        for table in TENANT_TABLES:
            assert ids(connection, table) == set(), table


def test_anon_reads_allergens_only(engine, two_shops):
    with as_user(engine, None) as connection:
        assert connection.scalar(text("select count(*) from allergens")) == 13
    for table in ["caterers", *TENANT_TABLES]:
        with as_user(engine, None) as connection, pytest.raises(ProgrammingError):
            connection.execute(text(f"select 1 from {table}"))  # noqa: S608


@pytest.mark.parametrize(
    "statement",
    [
        "update orders set status = 'approved'",
        "delete from customers",
        "insert into dish_categories (caterer_id, name) values (:caterer, 'x')",
        "update caterers set name = 'x'",
    ],
)
def test_caterer_cannot_write_through_the_api(engine, two_shops, statement):
    a, _ = two_shops
    with as_user(engine, a.tenant.user_id) as connection, pytest.raises(ProgrammingError):
        connection.execute(text(statement), {"caterer": a.tenant.id})


def test_helper_is_not_in_the_exposed_schema(session):
    schema = session.scalar(
        text("select pronamespace::regnamespace::text from pg_proc where proname = :name"),
        {"name": "current_caterer_id"},
    )
    assert schema == "private"


def test_every_table_has_rls_and_a_policy(session):
    tables = session.execute(
        text(
            "select c.relname, c.relrowsecurity, count(p.polname) "
            "from pg_class c left join pg_policy p on p.polrelid = c.oid "
            "where c.relnamespace = 'public'::regnamespace and c.relkind = 'r' "
            "group by c.relname, c.relrowsecurity"
        )
    ).all()
    assert tables
    for name, has_rls, policies in tables:
        assert has_rls, f"{name} has no RLS"
        assert policies, f"{name} has no policy, so no one can read it through the API"


def test_only_reads_are_granted_to_api_roles(session):
    grants = session.execute(
        text(
            "select grantee, table_name, privilege_type from information_schema.role_table_grants "
            "where table_schema = 'public' and grantee in ('anon', 'authenticated') "
            "and privilege_type <> 'SELECT'"
        )
    ).all()
    assert grants == []


def test_realtime_publishes_orders_only(session):
    tables = session.scalars(
        text("select tablename from pg_publication_tables where pubname = 'supabase_realtime'")
    ).all()
    assert tables == ["orders"]


def test_dish_photo_bucket_is_public_and_limited(session):
    bucket = session.execute(
        text("select public, file_size_limit from storage.buckets where id = 'caterer-assets'")
    ).one()
    assert bucket == (True, 5 * 1024 * 1024)
