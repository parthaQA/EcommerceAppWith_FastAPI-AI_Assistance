Technical Design Document (TDD): Fast_API Ecommerce Backend

1) Purpose
This document describes the architecture, modules, data models, APIs, configuration, and runtime behavior of the Fast_API backend application and also has unit testing in place to test the logic.

2) Scope
In scope
- FastAPI application structure and request flow
- Domain modules: customers, category, products, carts, orders
- Persistence via SQLAlchemy
- Validation/serialization via Pydantic
- Config via pydantic-settings and .env
- Caching via Redis (async)
- RabbitMQ for bulk product upload (async)
- Startup/shutdown behavior



3) Tech Stack
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- pydantic-settings
- Redis (async client)
- pytest for unit testing
- pytest-mock for mocking dependencies
- rabbitmq

4) High-Level Architecture
The app follows a feature-folder modular structure:

- Router layer (router.py): HTTP endpoints, request validation, dependencies.
- Controller layer (controller.py): business logic, DB operations, auth logic, caching logic.
- DTO layer (dtos.py): Pydantic schemas for input and output.
- Model layer (models.py): SQLAlchemy model definitions (tables/relationships).
- Utilities (src/utils/): shared DB session factory, settings, redis client, helpers, rabbitmq client.

Request Lifecycle (typical)
1. Client calls a route (example: /category/create)
2. Router validates request body (Pydantic schema)
3. Router injects DB session using Depends(get_db)
4. Router delegates to controller method
5. Controller queries/mutates DB models via SQLAlchemy session
6. Controller returns response object/dict (sometimes wrapped in ResponseSchema)
7. FastAPI serializes the response to JSON

5) Repository Layout
Fast_API/
  main.py
  requirement.txt
  .env
  src/
    utils/
      db.py
      settings.py
      redis.py
      helper.py
    customers/
      router.py
      controller.py
      dtos.py
      models.py
    category/
      router.py
      controller.py
      dtos.py
      models.py
    products/
      router.py
      controller.py
      dtos.py
      models.py
      carts/
      router.py
      controller.py
      dtos.py
      models.py
  tests/
    conftest.py
    test_customer.py
      

6) Application Entry Point (main.py)
Responsibilities
- Initializes SQLAlchemy tables using BASE.metadata.create_all(engine)
- Creates FastAPI app
- Includes routers:
  - customer_routes
  - category_routes
  - product_routes
  - cart_routes
  - order_routes
- Redis lifecycle:
  - startup: redis_client.ping()
  - shutdown: redis_client.close()
- Provides a simple Redis test endpoint:
  - GET /redis-test sets and gets a key

Note: create_all() is convenient for development but not ideal for production schema evolution (consider Alembic later).

7) Configuration & Secrets
Settings are loaded using pydantic-settings (src/utils/settings.py) from .env.

Expected environment variables
- DB_CONNECTION: SQLAlchemy DB URL
- SECRET_KEY: JWT signing key
- ALGORITHM: JWT algorithm (example: HS256)
- EXP_TIME: access token expiry time in minutes
- REDIS_URL: Redis connection URL (used in src/utils/redis.py)
- RABBITMQ_URL: RabbitMQ connection URL (used in src/utils/rabbitmq.py)

Security notes
- .env should not be committed to version control.
- SECRET_KEY must be strong and rotated appropriately.

8) Database Architecture (SQLAlchemy)
DB Session Management (src/utils/db.py)
- engine = create_engine(settings.DB_CONNECTION)
- Local_Session = sessionmaker(bind=engine)
- get_db() dependency yields a session and closes it in finally.

Tables and relationships

Category (src/category/models.py)
- Table: category
- Fields:
  - id (PK, autoincrement)
  - name (unique)
  - category_code (sequence starting at 1000)
  - image, description
  - created_date, modified_date
- Relationship:
  - CategoryModel.products ↔ ProductModel.category

Products (src/products/models.py)
- Table: products
- Fields:
  - product_id (PK, autoincrement)
  - product_name
  - product_description
  - product_price
  - product_quantity
  - category_id (FK → category.id)
  - created_date, modified_date
  - product_image_url (optional)

Customers (src/customers/models.py)
- Tables:
  - customers (CustomerModel)
  - customer_credential (CustomerRegistrationModel)
  - refresh_tokens (RefreshTokenModel)
- Notes:
  - CustomerModel.id is generated via helper
  - Credentials store hashed passwords
  - Refresh tokens are stored as hashed tokens with revocation fields

9) Redis Architecture
Redis Client (src/utils/redis.py)
- Uses redis.asyncio client created from REDIS_URL
- decode_responses=True so values are returned as strings
