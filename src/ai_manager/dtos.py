from pydantic import BaseModel


class ProductResponse(BaseModel):
    product_id: int
    name: str
    price: float
    available: bool
    quantity: int


class SearchResponse(BaseModel):
    query: str
    count: int
    products: list[ProductResponse]



def build_search_response(name: str, structured_products: list[dict]):
    return SearchResponse(
        query=name,
        count=len(structured_products),
        products=[
            ProductResponse(**p) for p in structured_products
        ]
    ).model_dump()