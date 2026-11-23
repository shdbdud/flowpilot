from fastapi import FastAPI, HTTPException
from backend.database import get_order_by_id
app = FastAPI(title="FlowPilot API")

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = get_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code= 404,
            detail= "Order not found"
        )
    return order
