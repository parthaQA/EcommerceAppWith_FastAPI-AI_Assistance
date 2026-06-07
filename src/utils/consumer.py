import json
import asyncio
import aio_pika
from sqlalchemy.orm import Session
from src.utils.db import Local_Session
from src.products.models import ProductModel
from src.category.models import CategoryModel

RABBITMQ_URL = "amqp://guest:guest@localhost/"

async def process_message(message):

    async with message.process():

        payload = json.loads(
            message.body.decode()
        )

        db: Session = Local_Session()

        try:

            is_exist = (
                db.query(ProductModel)
                .filter(
                    ProductModel.product_name ==
                    payload["product_name"]
                )
                .first()
            )

            if is_exist:
                return

            product = ProductModel(
                product_name=payload["product_name"],
                product_price=float(
                    payload["product_price"]
                ),
                product_quantity=int(
                    payload["product_quantity"]
                ),
                product_description=payload[
                    "product_description"
                ],
                category_id=payload["category_id"]
            )

            print(f"Processing: {payload['product_name']}")

            db.add(product)

            db.commit()

            print(f"Inserted: {payload['product_name']}")

        except Exception as e:
            db.rollback()
            print(f"Error: {e}")
            raise

        finally:
            db.close()



async def main():

    connection = await aio_pika.connect_robust(
        RABBITMQ_URL
    )

    channel = await connection.channel()

    queue = await channel.declare_queue(
        "product_bulk_queue",
        durable=True
    )

    await queue.consume(
        process_message
    )

    print("Consumer Started")

    await asyncio.Future()


if __name__ == "__main__":

    asyncio.run(main())