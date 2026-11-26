# FlowPilot Refund Policy (Demo)

| Field | Value |
| --- | --- |
| Policy version | 1.0 |
| Status | Demonstration policy for FlowPilot V1.0 |
| Implemented by | `backend/refund_rules.py` |
| Scope | Refund **eligibility screening** only |

> **Demo notice.** This document is a small, made-up policy used to exercise
> FlowPilot's deterministic rules. It is not a real company policy, contract,
> or legal advice.

## 1. Purpose

This policy defines when an order may enter the **human refund approval**
process. It does not approve refunds, move money, or replace human judgment.

The policy is intentionally limited to deterministic checks that can be
implemented and tested without an LLM, RAG, or external services.

<a id="refund-eligibility-rules"></a>

## 2. Policy rules

### R1 - 30-day refund window

A customer may request a refund within **30 calendar days after delivery**.

- The delivery day is **day 0**.
- **Day 30 is still inside the window.**
- **Day 31 is outside the window.**

The last eligible date ("deadline") is therefore
`delivered_at + 30 calendar days`, inclusive.

### R2 - Delivered orders only

Only orders whose status is exactly `delivered` enter the normal automatic
eligibility check. Orders in any other status (for example `pending`,
`processing`, `shipped`, `cancelled`) are sent to **human review**. They are
not automatically rejected, because a status change or a special case may
still require manual handling.

### R3 - Missing delivery date

If an order has no delivery date, the system **must not** treat it as
ineligible. The order goes to **human review**, and a human must establish the
delivery date before a decision can be made.

This also applies to blank, malformed, or impossible dates.

### R4 - Human approval is mandatory

An `eligible` result only means "this order may enter the approval process".
It is a **recommendation**, never an approval. A human must review and approve
or reject every refund proposal. The AI cannot bypass this step.

### R5 - Every decision needs a reason

Every result must state the outcome, a clear human-readable reason, the order
identifier, and the policy version/reference used.

### R6 - No automatic refunds

This policy never authorizes a real refund or any money movement. The
eligibility module is read-only: it has no payment side effects and writes
nothing to the database.

## 3. Date and time conventions

The exact conventions matter for the day-30 boundary, so they are fixed here:

| Item | Convention |
| --- | --- |
| `delivered_at` storage | ISO 8601 calendar date, `YYYY-MM-DD`, stored as SQLite `TEXT` |
| Time of day | Not stored. Delivery is treated as a whole calendar date. |
| Time zone | **UTC**. "Today" is the current UTC calendar date. |
| Day numbering | Delivery day = day 0 |
| Window | `0 <= days_since_delivery <= 30` |
| Deadline | `delivered_at + 30 days`, inclusive |
| Future delivery date | Data anomaly -> human review (never eligible) |

UTC is used so the result does not depend on the machine's local time zone or
on daylight-saving transitions. A real deployment could choose a business
time zone, but that would be a conscious policy change and a new policy
version, not an implementation detail.

Example for an order delivered on **2026-11-01**:

| Date | Day | Outcome |
| --- | --- | --- |
| 2026-11-01 | 0 | inside window |
| 2026-11-15 | 14 | inside window |
| 2026-11-30 | 29 | inside window |
| 2026-12-01 | 30 | **inside window (last eligible day)** |
| 2026-12-02 | 31 | **outside window** |

## 4. Decision outcomes

| Outcome | Meaning |
| --- | --- |
| `eligible` | The order satisfies the demo policy and may enter human approval. This is **not** an approved refund. |
| `ineligible` | Complete and valid order data proves the order fails the policy (delivered and day 31 or later). |
| `needs_review` | Data is missing, invalid, inconsistent, unknown, or the status is not suitable for automatic screening. A human must decide. |

Missing information is **never** converted into `ineligible`.

## 5. Evaluation order

Rules are evaluated in this order; the first matching rule wins:

1. Does the order exist? If not -> `needs_review` (the HTTP API returns 404
   for an unknown order instead of a decision).
2. Is the status exactly `delivered`? If not -> `needs_review`.
3. Is `delivered_at` present and non-blank? If not -> `needs_review`.
4. Is `delivered_at` a valid `YYYY-MM-DD` date? If not -> `needs_review`.
5. Is `delivered_at` after the evaluation date? If yes -> `needs_review`.
6. Is `(evaluation_date - delivered_at).days <= 30`?
   - yes -> `eligible`
   - no -> `ineligible`

## 6. Explicitly out of scope

This policy and its implementation do **not** cover:

- the actual refund decision or payment execution;
- partial refunds, shipping fees, taxes, or currency rules;
- fraud checks, chargebacks, or customer history;
- approval roles, escalation paths, or ticket creation;
- legal retention requirements.

## 7. Versioning

Any change to the window, the day-0 convention, the time zone, the status
mapping, or the evaluation order requires a new policy version and matching
updates in `backend/refund_rules.py`, tests, and this document.
