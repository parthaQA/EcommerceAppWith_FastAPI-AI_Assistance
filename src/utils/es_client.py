# es_client.py
from elasticsearch import Elasticsearch  # sync client, matches your sync SQLAlchemy style

es = Elasticsearch("http://localhost:9200")

PRODUCT_INDEX = "products"

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "product_id": {"type": "integer"},
            "product_name": {"type": "text"},
            "product_price": {"type": "float"},
            "product_quantity": {"type": "integer"},
        }
    }
}

class ESClient:

    @staticmethod
    def create_index_if_not_exists():
        if not es.indices.exists(index=PRODUCT_INDEX):
            try:
                es.indices.create(index=PRODUCT_INDEX, mappings=INDEX_MAPPING["mappings"])
            except Exception as e:
                print("ES error detail:", getattr(e, "info", str(e)))
                raise