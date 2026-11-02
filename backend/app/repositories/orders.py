import sqlite3


def insert_order(conn: sqlite3.Connection, order: dict, items: list[dict]) -> None:
    """Caller owns the transaction (`with conn:`)."""
    conn.execute(
        "INSERT INTO orders (id, status, customer_name, customer_phone, event, subtotal,"
        " delivery_fee, total, created_at) VALUES (:id, :status, :customer_name,"
        " :customer_phone, :event, :subtotal, :delivery_fee, :total,"
        " :created_at)",
        order,
    )
    conn.executemany(
        "INSERT INTO order_items (order_id, dish_id, quantity, snapshot_name,"
        " snapshot_unit_price, snapshot_line_total) VALUES (:order_id, :dish_id,"
        " :quantity, :snapshot_name, :snapshot_unit_price, :snapshot_line_total)",
        items,
    )
