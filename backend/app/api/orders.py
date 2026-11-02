import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.db import get_db
from app.schemas.orders import OrderIn
from app.services.orders import OrderError, submit_order

router = APIRouter(prefix="/api/orders")


@router.post("", status_code=201)
def create_order(order_in: OrderIn, conn: sqlite3.Connection = Depends(get_db)):  # noqa: B008
    try:
        result = submit_order(conn, order_in)
    except OrderError as err:
        body = {"error": {"code": err.code, "message": err.message, "details": {}}}
        return JSONResponse(body, status_code=422)
    order = result["order"]
    return {
        "id": order["id"],
        "status": order["status"],
        "lines": [
            {
                "dishId": line["dish_id"],
                "name": line["snapshot_name"],
                "qty": line["quantity"],
                "unitPrice": line["snapshot_unit_price_agorot"] / 100,
                "lineTotal": line["snapshot_line_total_agorot"] / 100,
            }
            for line in result["lines"]
        ],
        "subtotal": order["subtotal_agorot"] / 100,
        "deliveryFee": order["delivery_fee_agorot"] / 100,
        "total": order["total_agorot"] / 100,
        "submittedAt": order["created_at"],
    }
