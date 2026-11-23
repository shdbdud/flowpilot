# FlowPilot

**A work-in-progress AI-powered after-sales workflow assistant.**

FlowPilot is being built as a small-business after-sales support system. The intended workflow is to retrieve an order, consult a relevant after-sales policy, prepare a recommendation, request human approval, and create an auditable support ticket.

> **Current status — Milestone 1: Order Lookup API.** The repository currently implements a FastAPI order lookup endpoint backed by SQLite, plus automated API tests. It does **not** yet contain an LLM agent, RAG pipeline, approval system, or ticket creation workflow.

## What works today

- Look up an order by ID using `GET /orders/{order_id}`.
- Store and retrieve orders with SQLite.
- Initialize the database and insert one demo order (`A1001`) without duplicating it.
- Return `404` with a clear error message for unknown order IDs.
- Run isolated HTTP API tests using FastAPI `TestClient` and `pytest`.

## Tech stack

- **Language:** Python 3.12 (tested locally)
- **API:** FastAPI, Uvicorn
- **Database:** SQLite (`sqlite3` from the Python standard library)
- **Tests:** pytest, FastAPI TestClient (HTTPX)

## Project structure

```text
flowpilot/
├── backend/
│   ├── main.py          # FastAPI app and GET /orders/{order_id}
│   └── database.py      # Database initialization, demo data and order lookup
├── tests/
│   └── test_orders.py   # Existing/missing order API tests
├── data/                # Created locally during database initialization; not tracked
├── .gitignore
└── README.md
```

## Run locally

From the repository root, create and activate a virtual environment. The following commands use **Windows PowerShell**:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn pytest httpx
```

Initialize the database and seed the demo order:

```powershell
.\.venv\Scripts\python.exe -m backend.database
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 18080
```

The app is then available at:

- API docs: <http://127.0.0.1:18080/docs>
- Demo order: <http://127.0.0.1:18080/orders/A1001>
- Missing order: <http://127.0.0.1:18080/orders/A9999>

> Database initialization is currently a separate explicit command. Run it before starting the API on a fresh checkout. Port `18080` is used here because the development machine could not bind the default port `8000`; this is a local configuration choice, not a server requirement.

### Example response

`GET /orders/A1001` → `200 OK`

```json
{
  "order_id": "A1001",
  "customer": "Alice",
  "product": "Keyboard",
  "amount_cents": 19900,
  "status": "delivered"
}
```

Amounts are stored as integer minor currency units (`amount_cents`) rather than floating-point values. The current demo does not define a currency field.

`GET /orders/A9999` → `404 Not Found`

```json
{"detail": "Order not found"}
```

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

The two current tests check successful order retrieval and the 404 response. Each test redirects database access to an isolated temporary SQLite file using `tmp_path` and `monkeypatch`, so tests do not modify the local development database.

## Planned milestones

1. **Completed:** SQLite-backed order lookup API and basic tests.
2. After-sales policy data and deterministic business rules.
3. Tool registry/runtime and policy retrieval (RAG).
4. LLM-based recommendation with evidence and explicit human approval.
5. After-sales ticket creation, audit logs, error recovery and deployment.

## Development notes

This repository is an early learning/prototype project, **not a production-ready customer service system**. In particular, the current API has no authentication or authorization, the database uses local demo data, and there is no refund execution. Do not expose the development server publicly or put real customer information in the demo database.

Local database files, Python environments, caches and secret-containing `.env` files are excluded from version control.
