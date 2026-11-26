from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from backend import database
from backend.refund_rules import evaluate_refund_eligibility


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Safe and idempotent: creates the schema on a fresh install and upgrades
    # a Milestone 1 database in place before the first request is served.
    database.init_db()
    yield


app = FastAPI(title="FlowPilot API", version="0.2.0", lifespan=lifespan)


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = database.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    return order


@app.get("/orders/{order_id}/refund-eligibility")
def check_refund_eligibility(order_id: str):
    """Return a deterministic screening result. Read-only, no refund action."""
    order = database.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    return evaluate_refund_eligibility(order, order_id=order_id).as_dict()
