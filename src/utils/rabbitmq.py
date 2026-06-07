import json
import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost/"


class RabbitMQ:

    connection = None
    channel = None

    @classmethod
    async def connect(cls):
        cls.connection = await aio_pika.connect_robust(
            RABBITMQ_URL
        )

        cls.channel = await cls.connection.channel()

        await cls.channel.declare_queue(
            "product_bulk_queue",
            durable=True
        )

    @classmethod
    async def publish(cls, message):
        await cls.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="product_bulk_queue"
        )