import sqlite3

import pytest

from app.api.orders import SqliteOrders


def test_catalog_uses_foreign_keys_and_integer_ids(conn):
    dish = conn.execute("SELECT * FROM dishes WHERE legacy_code='d1'").fetchone()
    assert isinstance(dish['id'], int)
    assert 'metadata' not in dish.keys()
    with pytest.raises(sqlite3.IntegrityError, match='FOREIGN KEY'):
        conn.execute('UPDATE dishes SET category_id=999999 WHERE id=?', (dish['id'],))
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []


def test_allergens_are_per_allergen_and_unknown_is_not_free(conn):
    dish_id = conn.execute("SELECT id FROM dishes WHERE legacy_code='d2'").fetchone()[0]
    catalog = SqliteOrders(conn).catalog()
    dish = next(d for d in catalog['dishes'] if d['id'] == 'd2')
    assert all(a['status'] == 'unknown' for a in dish['metadata']['allergenStatuses'])
    allergen_id = conn.execute('SELECT id FROM allergens ORDER BY id LIMIT 1').fetchone()[0]
    conn.execute('INSERT INTO dish_allergens VALUES (?,?,?)', (dish_id, allergen_id, 'free'))
    dish = next(d for d in SqliteOrders(conn).catalog()['dishes'] if d['id'] == 'd2')
    assert dish['metadata']['allergenStatuses'][0]['status'] == 'free'
    with pytest.raises(sqlite3.IntegrityError, match='CHECK'):
        conn.execute("UPDATE dish_allergens SET status='safe' WHERE dish_id=?", (dish_id,))


def test_catalog_price_has_one_authoritative_source(conn):
    conn.execute("UPDATE dishes SET price_minor=12345 WHERE legacy_code='d1'")
    dish = next(d for d in SqliteOrders(conn).catalog()['dishes'] if d['id'] == 'd1')
    assert dish['price_minor'] == 12345
    assert 'price' not in dish['metadata']


def test_portion_recommendation_survives_normalization(conn):
    dish = next(d for d in SqliteOrders(conn).catalog()['dishes'] if d['id'] == 'd9')
    assert dish['metadata']['perGuest'] == 0.6
