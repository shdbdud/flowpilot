
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "flowpilot.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                product TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
                status TEXT NOT NULL
            )
        """)

def seed_order():
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute(
            """
            INSERT INTO orders (
                order_id, customer, product,
                amount_cents, status
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO NOTHING
            """,
            ("A1001", "Alice", "Keyboard", 19900, "delivered")
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
