from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from src.ai_manager.dtos import build_search_response
from src.products.controller import ProductController


class Tools:

    @staticmethod
    def get_search_product_tool(db):
        """Search products by name"""

        @tool
        def search_product(name: str, state: Annotated[dict, InjectedState]) -> dict:
            """Search products by name. it returns a list of products that match the search query."""

            customer_id = state["customer_id"]

            access_token = state["access_token"]

            print(
                f"Customer={customer_id}"
            )

            print(
                f"Token={access_token[:15]}"
            )

            print("name : ", name)

            product_details = ProductController.search_product_by_name(name, db)

            structured_products = [
                {
                    "name": p.product_name,
                    "price": p.product_price,
                    "available": p.product_quantity > 0
                }
                for p in product_details["data"]
            ]

            return build_search_response(name, structured_products)

        return search_product
