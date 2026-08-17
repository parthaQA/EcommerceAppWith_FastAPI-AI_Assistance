from typing import Annotated

from fastapi import HTTPException
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from sqlalchemy.orm import Session

from src.ai_manager.dtos import build_search_response
from src.cart.controller import CartController
from src.cart.dtos import CartItemSchema, ProductResponseSchema, CartProductsResponseSchema, CartProductSchema
from src.cart.models import CartModel, CartItemModel
from src.customers.models import CustomerModel
from src.products.controller import ProductController
from src.products.models import ProductModel
from langgraph.types import  Command, interrupt
from langsmith import traceable

from src.utils.helper import Helper
from langgraph.runtime import Runtime

class Tools:


    @staticmethod
    def get_search_product_tool(customer_id, db: Session):

        """Search products by name"""

        @tool
        @traceable
        def search_product(
                name: str,
                state: Annotated[dict, InjectedState]
        ) -> dict:
            """
               Search grocery products by product name.

               Use this tool whenever the user asks:
               - Find products
               - Check availability
               - Show prices

               Returns:
               Product name
               Price
               Availability
               """

            # customer_id = state["customer_id"]
            #
            # access_token = state["access_token"]

            print(
                f"Customer={customer_id}"
            )

            print("name : ", name)

            product_details = ProductController.search_product_by_name(name, db)

            structured_products = [
                {
                    "name": p.product_name,
                    "price": p.product_price,
                    "available": p.product_quantity > 0,
                    "quantity": p.product_quantity,
                    "product_id": p.product_id,
                }
                for p in product_details["data"]
            ]

            state["search_results"] = structured_products

            memory = state.get("product_memory", {})

            for p in structured_products:
                memory[p["name"].lower()] = p

            state["product_memory"] = memory

            return {
                **build_search_response(name, structured_products),
                "product_memory": memory
            }

        return search_product

    @staticmethod
    def add_product_to_cart_llm(customer_id, db: Session):

        @tool
        @traceable
        def add_product_to_cart(product_name: str,
        state: Annotated[dict, InjectedState], quantity: int = 1):

            """
                       add  products to cart.

                       Use this tool whenever the user asks:
                       - add products to cart
                       - Check the searched product is already available in product memory
                       - if avaiable use the products from product memory.

                       Returns:
                       cart details where product name, price are mentioned """

            # customer_id = state["customer_id"]

            location = state["location"]

            memory = state.get("product_memory", {})

            print("memory :", memory)

            product = memory.get(product_name.lower())

            print("product details : ", product)

            if not product:
                return {
                    "success": False,
                    "message": "Product not found in previous search."
                }

            product_id = product["product_id"]



            customer_exists = (
                db.query(CustomerModel)
                .filter(CustomerModel.id == customer_id)
                .first()
            )

            if not customer_exists:
                raise HTTPException(
                    status_code=404,
                    detail="Customer not found"
                )

            cart = (
                db.query(CartModel)
                .filter(
                    CartModel.customer_id == customer_id
                )
                .first()
            )

            if cart:
                cart_id = cart.cart_id
            else:
                cart_id = Helper.generate_cart_id()

                cart = CartModel(
                    cart_id=cart_id,
                    customer_id=customer_id,
                    location=location,
                )

                db.add(cart)
                db.commit()
                db.refresh(cart)



            if  product["quantity"] < quantity:
                raise HTTPException(
                status_code=400,
                detail="quantity not available"
            )

            cart_products = CartItemModel(
            cart_id=cart_id,
            product_id=product_id,
            quantity=quantity,
            is_checkout=True,
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

            cart_response = CartProductsResponseSchema(
                cart_id=cart_id,
                total_bill=total_bill,
                total_product_quantity=total_quantity,
                cart_products=CartProductSchema(product_details=products),
            )

            return {
                "success": True,
                "data": cart_response.model_dump(),  # <-- convert to dict
                "message": "product is added to cart"
            }


        return add_product_to_cart

    @staticmethod
    @tool
    def human_assistance(query: str):
        """request human assistance from human
        call this tool when user requires human assistance.
        llm should not provide any assistance"""
        human_response = interrupt({"query": query})
        return human_response["data"]

    @staticmethod
    def get_cart_tool(db: Session):

        @tool
        @traceable
        def get_cart(
                state: Annotated[dict, InjectedState]
        ):
            """call this tool to get the latest cart details
            the cart contains all the latest product details are
            added to cart."""
            cart_id = state["cart"]["cart_id"]

            cart_details = CartController.get_cart_for_checkout(cart_id, db)

            return {
                "data": cart_details["data"]
            }


        return get_cart