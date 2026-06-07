from os import access
import uuid
from fastapi import HTTPException, Request
from src.cart.models import CartItemModel, CartModel, DeliveryAddressModel
from src.customers.controller import CustomerController
from src.order.dtos import OrderSchema
from src.order.models import OrderItemModel, OrderModel
from src.utils.enum import OrderStatus, PaymentMode, PaymentStatus
from sqlalchemy.orm import Session

class OrderController:

    @staticmethod
    def create_order(request: Request, body: OrderSchema, db: Session):

        customer_authenticated = CustomerController.is_authenticated(request)

        if customer_authenticated["message"] != "Authenticated":
            return {
                "success": False,
                "data": [],
                "message": "Customer not authenticated"
            }
        cart = (
        db.query(CartModel)
        .filter(CartModel.cart_id == body.cart_id)
        .first()
    )
        if not cart:
            raise HTTPException(
        status_code=404,
        detail="Cart not found"
        )

        delivery_address = (
            db.query(DeliveryAddressModel)
            .filter(DeliveryAddressModel.cart_id==body.cart_id)
        ).first()

        if not delivery_address:
            raise HTTPException(
                status_code=400, 
                details= "delivery address is not added"
            )

        cart_items = (
        db.query(CartItemModel)
        .filter(CartItemModel.cart_id == body.cart_id)
        .all()
        )

        if not cart_items:
            raise HTTPException(
        status_code=400,
        detail="Cart is empty"
    )
        
        create_order = OrderModel(
        id=f"ORD{uuid.uuid4().hex[:8].upper()}",
        cart_id=body.cart_id,
        address_id=delivery_address.id,
        payment_mode=PaymentMode.COD,
        order_status=OrderStatus.PENDING,
        payment_status=PaymentStatus.UNPAID
        )      
    
        db.add(create_order)
        db.flush()

        cart_items = (
        db.query(CartItemModel)
        .filter(CartItemModel.cart_id == body.cart_id)
        .all()
        )

        for item in cart_items:
            db.add(
                OrderItemModel(
                order_id=create_order.id,
                product_id=item.product_id,
                quantity=item.quantity
            )
        )

        db.commit()
        db.refresh(create_order)

        return {
            "success": True,
            "data": create_order,
            "message": "Order created successfully"
        }   



