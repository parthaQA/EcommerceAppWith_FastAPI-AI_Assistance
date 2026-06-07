from pydantic import BaseModel, Field


class OrderSchema(BaseModel):
   cart_id:str = Field(..., strict=True)