from typing import Annotated
from fastapi import APIRouter, Depends, status, Request, Query
from src.order.controller import OrderController
from src.order.dtos import OrderSchema
from src.utils.db import get_db
from sqlalchemy.orm import Session

order_routes = APIRouter(prefix="/order")


@order_routes.post(path="/create", status_code=status.HTTP_201_CREATED, summary="Create a new customer")
def create_customer(request: Request, body: OrderSchema, db: Session=Depends(get_db)):
    return OrderController().create_order(request, body, db)


@order_routes.get(path="/order-details", status_code=status.HTTP_200_OK, summary="Get order details by order id")
def get_order_details_by_order_id(request: Request, order_id: Annotated[str, Query(...)], db: Session=Depends(get_db)):
    return OrderController().get_order_details_by_order_id(request, order_id, db)


