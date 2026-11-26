"""SQLite access for FlowPilot.

Milestone 2 adds a nullable `delivered_at` column to `orders`. Databases
created by Milestone 1 are upgraded in place with an additive, idempotent
migration; the table is never dropped, rebuilt, or back-filled.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "flowpilot.db"

CREATE_ORDERS_TABLE = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer TEXT NOT NULL,
        product TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
        status TEXT NOT NULL,
        delivered_at TEXT
    )
"""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the column names currently present in `table`."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_delivered_at_column(conn: sqlite3.Connection) -> bool:
    """Add `orders.delivered_at` to an older database if it is missing.

    Returns True when the column was added, False when it already existed.
    The migration is intentionally additive: `ALTER TABLE ... ADD COLUMN`
    keeps every existing row and value untouched. Re-running it is a no-op.
    """
    columns = _table_columns(conn, "orders")
    if not columns:
        raise RuntimeError("orders table is missing; create it before migrating")

    if "delivered_at" in columns:
        return False

    try:
        conn.execute("ALTER TABLE orders ADD COLUMN delivered_at TEXT")
    except sqlite3.OperationalError as exc:
        # Two processes may race on startup. If the other one won, the
        # column is already there and there is nothing left to do.
        if "duplicate column name" not in str(exc).lower():
            raise
        return False
    return True


def init_db() -> None:
    """Create the schema if needed and migrate older databases in place."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        # Wait instead of failing immediately if another process is writing.
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute(CREATE_ORDERS_TABLE)
        ensure_delivered_at_column(conn)


def seed_order() -> int:
    """Insert the demo order once. Existing rows are never overwritten.

    `delivered_at` is deliberately left NULL: the demo policy treats a missing
    delivery date as "human review", and inventing a date would fabricate
    business data. Set a date manually if you want to demo the window rules.
    """
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute(
            """
            INSERT INTO orders (
                order_id, customer, product,
                amount_cents, status, delivered_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO NOTHING
            """,
            ("A1001", "Alice", "Keyboard", 19900, "delivered", None)
        )
        return result.rowcount


def get_order_by_id(order_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return dict(row)


if __name__ == "__main__":
    init_db()
    inserted = seed_order()
    print("Inserted rows:", inserted)

    print(get_order_by_id("A1001"))
    print(get_order_by_id("A9999"))
