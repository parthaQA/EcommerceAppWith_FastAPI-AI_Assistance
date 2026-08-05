from sqlalchemy.orm import Session
from fastapi import HTTPException, Request
from src.cart.dtos import CartItemSchema, DeliveryAddressSchema, ProductResponseSchema, CartProductsResponseSchema, \
    CartProductSchema, CartResponseSchema
from src.cart.models import CartModel, CartItemModel, DeliveryAddressModel
from src.customers.controller import CustomerController
from src.customers.models import CustomerModel
from src.products.models import ProductModel
from src.utils.helper import Helper


class CartController:

    @staticmethod
    def get_cart(request: Request, location: str, db: Session):
        customer_id_header = request.headers.get("customer_id")
        customer_exists = db.query(CustomerModel).filter(CustomerModel.id == customer_id_header).first()
        if not customer_exists:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer_authenticated = CustomerController.is_authenticated(request)

        if customer_authenticated["message"] != "Authenticated":
            return {
                "success": False,
                "data": [],
                "message": "Customer not authenticated"
            }
        cart_id = Helper.generate_cart_id()
        cart = CartModel(cart_id=cart_id, location=location, customer_id=customer_id_header)
        db.add(cart)
        db.commit()
        db.refresh(cart)

        return {
            "success": True,
            "data": CartResponseSchema(cart_id=cart.cart_id, location=cart.location, created_date=cart.created_date,
                                       modified_date=cart.modified_date),
            "message": "Cart retrieved successfully"
        }

    
    @staticmethod
    def add_product_to_cart(request: Request, cart_id: str, body: CartItemSchema, db: Session):

        customer_authenticated = CustomerController.is_authenticated(request)

        if customer_authenticated["message"] != "Authenticated":
            return {
                "success": False,
                "data": [],
                "message": "Customer not authenticated"
            }
        is_cart_exists = db.query(CartModel).filter(CartModel.cart_id== cart_id).first()
        if not is_cart_exists:
            raise HTTPException(status_code=404, detail= "cart id not found")

        is_product_exist = db.query(ProductModel).filter(ProductModel.product_id==body.product_id).first()

        if not is_product_exist:
            raise HTTPException(status_code=404, detail="product id does not exist")
        
        if is_product_exist.product_quantity < body.quantity:
            raise HTTPException(
            status_code=400,
            detail="quantity not available"
            )
    
        
        cart_products = CartItemModel(
            cart_id=cart_id,
            product_id=body.product_id,
            quantity=body.quantity,
            is_checkout=body.is_checkout,
        )
        db.add(cart_products)
        db.commit()
        db.refresh(cart_products)

        # fetch all products in cart
        cart_items = (
        db.query(CartItemModel)
        .filter(CartItemModel.cart_id == cart_id)
        .all()
        )
        
        products = []
        total_bill = 0
        total_quantity = 0


        for item in cart_items:
            prod = db.query(ProductModel).filter(
            ProductModel.product_id == item.product_id
            ).first()

            products.append(ProductResponseSchema(
                product_id=prod.product_id,
                product_name=prod.product_name,
                product_description=prod.product_description,
                product_price=prod.product_price,
                product_quantity=item.quantity,
            ))

            total_bill += prod.product_price * item.quantity
            total_quantity += item.quantity


        return {
            "success": True,
            "data": CartProductsResponseSchema(
                cart_id=cart_id,
                total_bill=total_bill,
                total_product_quantity=total_quantity,
                cart_products=CartProductSchema(product_details=products),
            ),
            "message": "product is added to cart"
        }


    @staticmethod
    def add_delivery_address(request: Request, cart_id: str, body: DeliveryAddressSchema, db: Session):
        
        customer_authenticated = CustomerController.is_authenticated(request)

        if customer_authenticated["message"] != "Authenticated":
            return {
                "success": False,
                "data": [],
                "message": "Customer not authenticated"
            }
        
        is_cart_exists = db.query(CartModel).filter(CartModel.cart_id== cart_id).first()
        if not is_cart_exists:
            raise HTTPException(status_code=404, detail= "cart id not found")

        if not (560001 <= body.pincode <= 560114):
            raise HTTPException(
            status_code=400,
            detail="Delivery is available only for pincodes between 560001 and 560114"
        )


        delivery_address = DeliveryAddressModel(
            cart_id=cart_id,
            address=body.address,
            pincode=body.pincode,
            city=body.city,
        )
        db.add(delivery_address)
        db.commit()
        db.refresh(delivery_address)

        return {
            "success": True,
            "data": delivery_address,
            "message": "Delivery address added successfully"
        }


    @staticmethod
    def get_cart_for_checkout(cart_id, db: Session):

        is_cart_exists = db.query(CartModel).filter(CartModel.cart_id == cart_id).first()
        if not is_cart_exists:
            raise HTTPException(status_code=404, detail="cart id not found")

        results = (
            db.query(CartItemModel, ProductModel)
            .join(
                ProductModel,
                CartItemModel.product_id == ProductModel.product_id
            )
            .filter(CartItemModel.cart_id == cart_id)
            .all()
        )

        cart_products = []

        for cart_item, product in results:
            cart_products.append({
                "product_id": product.product_id,
                "product_name": product.product_name,
                "product_description": product.product_description,
                "product_price": product.product_price,
                "product_quantity": cart_item.quantity,
                "product_image_url": product.product_image_url
            })

        return {
            "data": cart_products
        }
