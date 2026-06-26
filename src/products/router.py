from fastapi import APIRouter, status, Depends, UploadFile, File, Query, Request, HTTPException
from sqlalchemy.orm import Session
from watchfiles import awatch

from src.customers.controller import CustomerController
from src.customers.models import CustomerModel
from src.products.controller import ProductController
from src.products.dtos import ProductSchema, ProductResponseSchema
from src.utils.db import get_db
from typing import Annotated

product_routes=APIRouter(prefix="/products")



@product_routes.post("/{category_id}/add", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
def add_product_by_category_id(category_id: int, body: ProductSchema, db: Session= Depends(get_db)):
    return ProductController.add_product_by_category_id(
        category_id= category_id,body=body, db=db)


@product_routes.post("/{category_id}/bulk-add", status_code=status.HTTP_201_CREATED)
async def add_product_in_bulk(category_id: int, file : UploadFile = File(...), db: Session= Depends(get_db)):
    return await ProductController.add_bulk_products_by_csv(
        category_id= category_id, file=file,db= db)

@product_routes.get("/all", status_code=status.HTTP_200_OK)
def get_all_products(limit: Annotated[int, Query(...)] = 10, db: Session= Depends(get_db)):
    return ProductController.get_all_products(limit, db)

@product_routes.get("/{product_id}", status_code=status.HTTP_200_OK)
async def get_product_by_id(product_id: int, db: Session= Depends(get_db)):
    return await ProductController.get_product_by_product_id(product_id=product_id, db=db)


@product_routes.patch("/{product_id}", status_code=status.HTTP_200_OK, response_model=ProductResponseSchema)
def update_a_product_by_id(product_id: int, body: ProductSchema, db: Session= Depends(get_db)):
    return ProductController.update_a_product_by_id(product_id=product_id, body=body, db=db)


@product_routes.get("", status_code=status.HTTP_200_OK)
def search_product(request: Request,
    name: str = Query(...),
    db: Session = Depends(get_db)
):
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
    return ProductController.search_product_by_name(name=name, db=db)