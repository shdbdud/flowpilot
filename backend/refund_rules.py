"""Deterministic refund eligibility rules for FlowPilot (Milestone 2).

This module implements `policies/refund_policy.md` version 1.0. It is pure
business logic: no LLM, no RAG, no payment calls, and no database writes.
The current date is injectable via `as_of` so tests never depend on the wall
clock.

Outcomes:
    eligible      - may enter human approval (NOT an approved refund)
    ineligible    - complete, valid data proves the policy is not met
    needs_review  - missing/invalid/anomalous data or a non-delivered status
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Mapping

from backend import database

POLICY_VERSION = "1.0"
POLICY_REFERENCE = "policies/refund_policy.md#refund-eligibility-rules"
REFUND_WINDOW_DAYS = 30

ELIGIBLE = "eligible"
INELIGIBLE = "ineligible"
NEEDS_REVIEW = "needs_review"

RefundStatus = Literal["eligible", "ineligible", "needs_review"]

_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, slots=True)
class RefundDecision:
    """One eligibility result. Pure data; creating it has no side effects."""

    order_id: str
    status: RefundStatus
    reason: str
    policy_version: str
    policy_reference: str
    evaluated_on: date
    days_since_delivery: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready representation used by the HTTP layer."""
        return {
            "order_id": self.order_id,
            "status": self.status,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "policy_reference": self.policy_reference,
            "evaluated_on": self.evaluated_on.isoformat(),
            "days_since_delivery": self.days_since_delivery,
        }


def _today_utc() -> date:
    """The policy clock: the current UTC calendar date (see policy section 3)."""
    return datetime.now(timezone.utc).date()


def _parse_delivery_date(value: object) -> date | None:
    """Parse a strict `YYYY-MM-DD` date; return None for anything else."""
    if not isinstance(value, str) or not _ISO_DATE_PATTERN.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        # Covers impossible dates such as 2026-02-30.
        return None


def _shorten(text: str, limit: int = 60) -> str:
    """Keep error messages readable even for very long malformed values."""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _decision(
    *,
    order_id: str,
    status: RefundStatus,
    reason: str,
    evaluated_on: date,
    days_since_delivery: int | None = None,
) -> RefundDecision:
    return RefundDecision(
        order_id=order_id,
        status=status,
        reason=reason,
        policy_version=POLICY_VERSION,
        policy_reference=POLICY_REFERENCE,
        evaluated_on=evaluated_on,
        days_since_delivery=days_since_delivery,
    )


def evaluate_refund_eligibility(
    order: Mapping[str, Any] | None,
    as_of: date | None = None,
    *,
    order_id: str | None = None,
) -> RefundDecision:
    """Evaluate one order against the demo refund policy.

    Args:
        order: A row from `orders` (dict-like), or None if not found.
        as_of: Evaluation date; defaults to the current UTC date.
        order_id: Fallback identifier used only when `order` is None.

    Returns:
        A `RefundDecision`. This function performs no I/O and cannot move money.
    """
    evaluated_on = as_of or _today_utc()

    resolved_id = ""
    if order is not None:
        resolved_id = str(order.get("order_id") or "")
    if not resolved_id and order_id:
        resolved_id = str(order_id)
    if not resolved_id:
        resolved_id = "<unknown>"

    # R3 (existence): never guess about an order we cannot see.
    if order is None:
        return _decision(
            order_id=resolved_id,
            status=NEEDS_REVIEW,
            reason=(
                f"No order record was found for order {resolved_id}; "
                "human review is required."
            ),
            evaluated_on=evaluated_on,
        )

    # R2: only `delivered` enters normal screening. Anything else is sent to
    # a human; a status change may still make the order refundable.
    status_value = order.get("status")
    if status_value != "delivered":
        shown_status = (
            repr(status_value) if status_value is not None else "missing"
        )
        return _decision(
            order_id=resolved_id,
            status=NEEDS_REVIEW,
            reason=(
                f"Order status is {shown_status}; only delivered orders are "
                "screened automatically, so human review is required."
            ),
            evaluated_on=evaluated_on,
        )

    # R3 (date): missing data must not become an automatic rejection.
    delivered_raw = order.get("delivered_at")
    if delivered_raw is None or (
        isinstance(delivered_raw, str) and not delivered_raw.strip()
    ):
        return _decision(
            order_id=resolved_id,
            status=NEEDS_REVIEW,
            reason=(
                "Order has no delivery date; the policy requires human review "
                "instead of an automatic rejection."
            ),
            evaluated_on=evaluated_on,
        )

    delivered_on = _parse_delivery_date(delivered_raw)
    if delivered_on is None:
        shown_value = _shorten(repr(delivered_raw))
        return _decision(
            order_id=resolved_id,
            status=NEEDS_REVIEW,
            reason=(
                f"Delivery date {shown_value} is not a valid ISO date "
                "(YYYY-MM-DD); human review is required."
            ),
            evaluated_on=evaluated_on,
        )

    # A delivery date in the future is inconsistent data, not an edge case.
    if delivered_on > evaluated_on:
        return _decision(
            order_id=resolved_id,
            status=NEEDS_REVIEW,
            reason=(
                f"Delivery date {delivered_on.isoformat()} is after the "
                f"evaluation date {evaluated_on.isoformat()}; the order data "
                "is inconsistent and needs human review."
            ),
            evaluated_on=evaluated_on,
        )

    days = (evaluated_on - delivered_on).days
    deadline = delivered_on + timedelta(days=REFUND_WINDOW_DAYS)

    if days > REFUND_WINDOW_DAYS:
        return _decision(
            order_id=resolved_id,
            status=INELIGIBLE,
            reason=(
                f"Order was delivered on {delivered_on.isoformat()} "
                f"({days} days ago, day {days}); the 30-day refund window "
                f"ended on {deadline.isoformat()} (day 30 was the last "
                "eligible day)."
            ),
            evaluated_on=evaluated_on,
            days_since_delivery=days,
        )

    if days == REFUND_WINDOW_DAYS:
        boundary_note = "day 30 is the last eligible day."
    else:
        boundary_note = f"the deadline is {deadline.isoformat()}."

    return _decision(
        order_id=resolved_id,
        status=ELIGIBLE,
        reason=(
            f"Order was delivered on {delivered_on.isoformat()} "
            f"({days} days ago, day {days}); within the 30-day refund window; "
            f"{boundary_note} Eligible to enter human approval, not approved."
        ),
        evaluated_on=evaluated_on,
        days_since_delivery=days,
    )


def get_refund_eligibility(
    order_id: str,
    *,
    as_of: date | None = None,
) -> RefundDecision:
    """Load an order from SQLite and evaluate it. Read-only."""
    order = database.get_order_by_id(order_id)
    return evaluate_refund_eligibility(order, as_of=as_of, order_id=order_id)
