"""HTTP tests for the read-only refund eligibility endpoint."""

import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend import refund_rules
from backend.main import app

TODAY = date(2026, 11, 25)


@pytest.fixture(autouse=True)
def fixed_policy_clock(monkeypatch):
    """The endpoint has no client-controlled date; freeze its clock in tests."""
    monkeypatch.setattr(refund_rules, "_today_utc", lambda: TODAY)


def setup_order(tmp_path, monkeypatch, delivered_at):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "api.db")
    database.init_db()
    database.seed_order()
    if delivered_at is not None:
        with sqlite3.connect(database.DB_PATH) as conn:
            conn.execute(
                "UPDATE orders SET delivered_at = ? WHERE order_id = ?",
                (delivered_at, "A1001"),
            )
    return TestClient(app)


@pytest.mark.parametrize(
    "days_ago, expected_status",
    [
        (0, "eligible"),
        (5, "eligible"),
        (30, "eligible"),
        (31, "ineligible"),
        (90, "ineligible"),
    ],
)
def test_refund_endpoint_window(
    tmp_path, monkeypatch, days_ago, expected_status
):
    delivered = (TODAY - timedelta(days=days_ago)).isoformat()
    client = setup_order(tmp_path, monkeypatch, delivered)

    response = client.get("/orders/A1001/refund-eligibility")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected_status
    assert body["order_id"] == "A1001"
    assert body["days_since_delivery"] == days_ago
    assert body["evaluated_on"] == TODAY.isoformat()
    assert body["policy_version"] == "1.0"
    assert body["policy_reference"].startswith("policies/refund_policy.md")


def test_refund_endpoint_missing_delivery_date(tmp_path, monkeypatch):
    client = setup_order(tmp_path, monkeypatch, None)

    response = client.get("/orders/A1001/refund-eligibility")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"
    assert body["days_since_delivery"] is None
    assert "no delivery date" in body["reason"].lower()


def test_refund_endpoint_unknown_order_is_404(tmp_path, monkeypatch):
    client = setup_order(tmp_path, monkeypatch, TODAY.isoformat())

    response = client.get("/orders/A9999/refund-eligibility")

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_refund_endpoint_is_read_only(tmp_path, monkeypatch):
    client = setup_order(tmp_path, monkeypatch, TODAY.isoformat())

    first = client.get("/orders/A1001/refund-eligibility").json()
    second = client.get("/orders/A1001/refund-eligibility").json()

    assert first == second
    with sqlite3.connect(database.DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count == 1


def test_existing_order_endpoint_still_returns_old_fields(tmp_path, monkeypatch):
    client = setup_order(tmp_path, monkeypatch, "2026-11-01")

    response = client.get("/orders/A1001")

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "A1001"
    assert body["customer"] == "Alice"
    assert body["product"] == "Keyboard"
    assert body["amount_cents"] == 19900
    assert body["status"] == "delivered"
    assert body["delivered_at"] == "2026-11-01"
