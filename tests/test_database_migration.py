"""Migration and API compatibility tests using temporary databases only."""

import sqlite3

from fastapi.testclient import TestClient

from backend import database
from backend.main import app

LEGACY_SCHEMA = """
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer TEXT NOT NULL,
        product TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
        status TEXT NOT NULL
    )
"""

LEGACY_ROW = ("A1001", "Legacy Alice", "Keyboard", 4999, "delivered")


def create_legacy_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(LEGACY_SCHEMA)
        conn.execute(
            """
            INSERT INTO orders (order_id, customer, product, amount_cents, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            LEGACY_ROW,
        )


def columns(path):
    with sqlite3.connect(path) as conn:
        return [row[1] for row in conn.execute("PRAGMA table_info(orders)")]


def test_init_db_creates_delivered_at_column(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "fresh.db")

    database.init_db()

    assert "delivered_at" in columns(database.DB_PATH)


def test_init_db_creates_missing_parent_directory(tmp_path, monkeypatch):
    db_path = tmp_path / "nested" / "deeper" / "fresh.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    database.init_db()

    assert db_path.exists()


def test_init_db_upgrades_legacy_database_without_data_loss(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    create_legacy_db(db_path)

    database.init_db()

    assert "delivered_at" in columns(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT order_id, customer, product, amount_cents, status, delivered_at
            FROM orders WHERE order_id = ?
            """,
            ("A1001",),
        ).fetchone()

    assert row == LEGACY_ROW + (None,)


def test_init_db_is_idempotent_and_preserves_data(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    create_legacy_db(db_path)

    database.init_db()
    database.init_db()
    database.init_db()

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        row = conn.execute(
            "SELECT customer, amount_cents FROM orders WHERE order_id = 'A1001'"
        ).fetchone()

    assert count == 1
    assert row == ("Legacy Alice", 4999)


def test_seed_does_not_overwrite_existing_data(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    create_legacy_db(db_path)
    database.init_db()

    inserted = database.seed_order()
    inserted_again = database.seed_order()

    assert inserted == 0
    assert inserted_again == 0
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT customer, amount_cents FROM orders WHERE order_id = 'A1001'"
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    assert row == ("Legacy Alice", 4999)
    assert count == 1


def test_upgraded_database_can_store_delivery_date(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    create_legacy_db(db_path)

    database.init_db()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE orders SET delivered_at = ? WHERE order_id = ?",
            ("2026-11-01", "A1001"),
        )

    assert database.get_order_by_id("A1001")["delivered_at"] == "2026-11-01"


def test_upgraded_database_keeps_order_api_working(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "legacy.db")
    create_legacy_db(database.DB_PATH)

    with TestClient(app) as client:  # lifespan runs init_db()
        response = client.get("/orders/A1001")

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "A1001"
    assert body["customer"] == "Legacy Alice"
    assert body["amount_cents"] == 4999
    assert body["status"] == "delivered"
    assert body["delivered_at"] is None


def test_app_startup_creates_fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "startup" / "fresh.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)

    with TestClient(app) as client:
        response = client.get("/orders/A9999")

    assert response.status_code == 404
    assert db_path.exists()
    assert "delivered_at" in columns(db_path)
