"""Unit tests for the deterministic refund rules (no database required)."""

import sqlite3
from datetime import date, timedelta

import pytest

from backend import database
from backend.refund_rules import (
    ELIGIBLE,
    INELIGIBLE,
    NEEDS_REVIEW,
    POLICY_REFERENCE,
    POLICY_VERSION,
    REFUND_WINDOW_DAYS,
    evaluate_refund_eligibility,
    get_refund_eligibility,
)

TODAY = date(2026, 11, 25)


def make_order(**overrides):
    order = {
        "order_id": "A1001",
        "customer": "Alice",
        "product": "Keyboard",
        "amount_cents": 19900,
        "status": "delivered",
        "delivered_at": TODAY.isoformat(),
    }
    order.update(overrides)
    return order


@pytest.mark.parametrize("days", [0, 1, 14, 29, REFUND_WINDOW_DAYS])
def test_delivered_inside_window_is_eligible(days):
    delivered = (TODAY - timedelta(days=days)).isoformat()
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=delivered), as_of=TODAY
    )

    assert decision.status == ELIGIBLE
    assert decision.days_since_delivery == days
    assert decision.order_id == "A1001"
    assert decision.policy_version == POLICY_VERSION
    assert decision.policy_reference == POLICY_REFERENCE
    assert "human approval" in decision.reason
    assert "not approved" in decision.reason


def test_day_30_is_the_last_eligible_day():
    delivered = TODAY - timedelta(days=30)
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=delivered.isoformat()), as_of=TODAY
    )

    assert decision.status == ELIGIBLE
    assert decision.days_since_delivery == 30
    assert "day 30 is the last eligible day" in decision.reason


def test_day_31_is_ineligible():
    delivered = TODAY - timedelta(days=31)
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=delivered.isoformat()), as_of=TODAY
    )

    assert decision.status == INELIGIBLE
    assert decision.days_since_delivery == 31
    assert "31 days ago" in decision.reason
    assert (TODAY - timedelta(days=1)).isoformat() in decision.reason


def test_long_expired_order_is_ineligible():
    delivered = TODAY - timedelta(days=365)
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=delivered.isoformat()), as_of=TODAY
    )

    assert decision.status == INELIGIBLE
    assert decision.days_since_delivery == 365


def test_missing_delivery_key_needs_review():
    order = make_order()
    del order["delivered_at"]

    decision = evaluate_refund_eligibility(order, as_of=TODAY)

    assert decision.status == NEEDS_REVIEW
    assert decision.days_since_delivery is None
    assert "no delivery date" in decision.reason.lower()
    assert "instead of an automatic rejection" in decision.reason


@pytest.mark.parametrize("value", [None, "", "   "])
def test_blank_delivery_date_needs_review(value):
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=value), as_of=TODAY
    )

    assert decision.status == NEEDS_REVIEW
    assert "no delivery date" in decision.reason.lower()


def test_future_delivery_date_needs_review():
    future = (TODAY + timedelta(days=1)).isoformat()
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=future), as_of=TODAY
    )

    assert decision.status == NEEDS_REVIEW
    assert "after the evaluation date" in decision.reason
    assert future in decision.reason


@pytest.mark.parametrize(
    "value",
    [
        "25/11/2026",
        "2026-2-3",
        "2026-02-30",
        "2026-11-25T10:00:00",
        "not-a-date",
        "20261125",
        20261125,
    ],
)
def test_malformed_delivery_date_needs_review(value):
    decision = evaluate_refund_eligibility(
        make_order(delivered_at=value), as_of=TODAY
    )

    assert decision.status == NEEDS_REVIEW
    assert "not a valid ISO date" in decision.reason


@pytest.mark.parametrize(
    "status",
    ["pending", "processing", "shipped", "cancelled", "Delivered", "", None],
)
def test_non_delivered_status_needs_review(status):
    decision = evaluate_refund_eligibility(
        make_order(status=status, delivered_at=TODAY.isoformat()),
        as_of=TODAY,
    )

    assert decision.status == NEEDS_REVIEW
    assert "human review is required" in decision.reason
    assert "delivered orders" in decision.reason


def test_missing_order_needs_review_and_keeps_identifier():
    decision = evaluate_refund_eligibility(None, as_of=TODAY, order_id="A9999")

    assert decision.status == NEEDS_REVIEW
    assert decision.order_id == "A9999"
    assert "No order record" in decision.reason


def test_missing_order_without_identifier_is_still_safe():
    decision = evaluate_refund_eligibility(None, as_of=TODAY)

    assert decision.status == NEEDS_REVIEW
    assert decision.order_id == "<unknown>"


def test_as_dict_is_json_ready_and_complete():
    decision = evaluate_refund_eligibility(make_order(), as_of=TODAY)
    payload = decision.as_dict()

    assert payload == {
        "order_id": "A1001",
        "status": ELIGIBLE,
        "reason": decision.reason,
        "policy_version": "1.0",
        "policy_reference": POLICY_REFERENCE,
        "evaluated_on": "2026-11-25",
        "days_since_delivery": 0,
    }


def test_evaluation_is_pure_and_repeatable():
    order = make_order(delivered_at="2026-11-20")
    first = evaluate_refund_eligibility(order, as_of=TODAY)
    second = evaluate_refund_eligibility(order, as_of=TODAY)

    assert first == second
    assert order["delivered_at"] == "2026-11-20"  # input was not mutated


def test_get_refund_eligibility_reads_temp_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rules.db")
    database.init_db()
    database.seed_order()

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            "UPDATE orders SET delivered_at = ? WHERE order_id = ?",
            ((TODAY - timedelta(days=7)).isoformat(), "A1001"),
        )

    decision = get_refund_eligibility("A1001", as_of=TODAY)

    assert decision.status == ELIGIBLE
    assert decision.days_since_delivery == 7


def test_get_refund_eligibility_unknown_order(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rules.db")
    database.init_db()

    decision = get_refund_eligibility("A9999", as_of=TODAY)

    assert decision.status == NEEDS_REVIEW
    assert decision.order_id == "A9999"


def test_demo_seed_has_no_delivery_date(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rules.db")
    database.init_db()
    database.seed_order()

    decision = get_refund_eligibility("A1001", as_of=TODAY)

    assert decision.status == NEEDS_REVIEW
    assert "no delivery date" in decision.reason.lower()
