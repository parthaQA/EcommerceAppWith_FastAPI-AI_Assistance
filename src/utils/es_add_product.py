
from src.utils.es_client import es, PRODUCT_INDEX, ESClient
from src.products.models import ProductModel
from src.category.models import CategoryModel
from src.utils.db import Local_Session

class ESAddProduct:

    @staticmethod
    def add_product_to_es():

        ESClient.create_index_if_not_exists()
        db = Local_Session()
        products = db.query(ProductModel).all()

        for product in products:
            es.index(
                index=PRODUCT_INDEX,
                id=str(product.product_id),
                document={
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "product_price": product.product_price,
                    "product_quantity": product.product_quantity,
                }
            )
        db.close()
        print(f"Indexed {len(products)} products")

    @staticmethod
    def get_es_product():

        response = es.search(
            index=PRODUCT_INDEX,
            query={
                "match_all": {}
            }
        )

        print(f"Total products: {response['hits']['total']}")

        for hit in response["hits"]["hits"]:
            print(hit["_source"])

if __name__ == "__main__":
    # ESAddProduct.add_product_to_es()
    ESAddProduct.get_es_product()