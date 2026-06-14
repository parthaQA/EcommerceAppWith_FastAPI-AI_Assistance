from fastapi import APIRouter, Depends, status, Query, Request, HTTPException
from sqlalchemy.orm import Session
from typing import Annotated
from src.cart.controller import CartController
from src.cart.dtos import CartResponseSchema, CartItemSchema, DeliveryAddressSchema
from src.utils.db import get_db


cart_routes = APIRouter(prefix="/cart")


@cart_routes.get(path="/get", status_code=status.HTTP_200_OK, summary="Get a new cart")
def get_cart(request: Request, location: Annotated[str, Query(...)], db: Session = Depends(get_db)):
   
    return CartController.get_cart(request,location, db)


@cart_routes.post(path="/{cart_id}/products/add", status_code=status.HTTP_201_CREATED, summary="Add a product to the cart")
def add_product_to_cart(request: Request, cart_id: str, body: CartItemSchema, db: Session = Depends(get_db)):
    return CartController.add_product_to_cart(request, cart_id, body, db)


@cart_routes.post(path="/{cart_id}/delivery/add-address", status_code=status.HTTP_200_OK, summary="add deilvery address from the cart")
def add_delivery_address(request: Request, cart_id: str, body: DeliveryAddressSchema, db: Session = Depends(get_db)):
    return CartController.add_delivery_address(request, cart_id, body, db)

