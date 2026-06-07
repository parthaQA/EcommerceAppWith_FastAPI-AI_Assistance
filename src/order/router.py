from fastapi import APIRouter, Depends, status, Request
from src.order.controller import OrderController
from src.order.dtos import OrderSchema
from src.utils.db import get_db
from sqlalchemy.orm import Session

order_routes = APIRouter(prefix="/order")


@order_routes.post(path="/create", status_code=status.HTTP_201_CREATED, summary="Create a new customer")
def create_customer(request: Request, body: OrderSchema, db: Session=Depends(get_db)):
    return OrderController().create_order(request, body, db)


# @order_routes.get(path="/all", response_model=List[CustomerResponseSchema], status_code=status.HTTP_200_OK, summary="Get all customers")
# def get_all_customers(db: Session=Depends(get_db)):
#     return CustomerController().get_all_customers(db)
