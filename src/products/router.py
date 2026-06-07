from fastapi import APIRouter, status, Depends, UploadFile, File, Query
from sqlalchemy.orm import Session
from watchfiles import awatch

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


