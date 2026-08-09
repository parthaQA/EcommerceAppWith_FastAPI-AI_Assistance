from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
import os
from dotenv import load_dotenv
from mem0 import Memory
from src.ai_manager.mem0_config import config


class DBManager:

    load_dotenv()


    DATABASE_URL = os.getenv("DB_CONNECTION")
    pool = ConnectionPool(conninfo=str(DATABASE_URL),
                              kwargs={"autocommit": True},
                              )

    checkpointer = PostgresSaver(pool)


    @classmethod
    def get_checkpointer(cls):
        return cls.checkpointer.setup()



    @staticmethod
    def initialize_mem0_memory():

        mem = Memory.from_config(config)
        return mem


    @staticmethod
    def insert_into_mem0_db(messages, customer_id):

        print("customer_id in insert_into_mem0_db :", customer_id)
        mem = DBManager.initialize_mem0_memory()

        try:
            result = mem.add(messages, user_id=customer_id)
            return result

        except Exception as e:
            print("Error inserting into mem0 database:", str(e))
            return None




    @staticmethod
    def retrieve_from_mem0_db(query, customer_id):

        mem = DBManager.initialize_mem0_memory()

        try:
            result = mem.search(
                query,
                filters={
                    "user_id": customer_id
                }
            )

            return result

        except Exception as e:
            print(
                "Error retrieving from mem0 database:",
                str(e)
            )
            return None



