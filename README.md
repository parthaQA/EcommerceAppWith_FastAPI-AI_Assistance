# Fast_API — E-Commerce Backend with Agentic AI Shopping Assistant

A full-stack grocery e-commerce platform built with **FastAPI** and an **agentic AI shopping assistant** powered by **LangGraph**, **LangChain**, and **Ollama**. The REST API handles customers, products, carts, and orders; the AI layer orchestrates natural-language shopping flows (search, cart, policy Q&A) via a LangGraph state machine with guardrails, RAG, and tool calling.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [AI Shopping Assistant](#ai-shopping-assistant)
  - [Design Pattern](#design-pattern)
  - [LangGraph Workflow](#langgraph-workflow)
  - [Intent Routing](#intent-routing)
  - [RAG Pipeline](#rag-pipeline)
  - [Agent Tools](#agent-tools)
  - [State & Memory](#state--memory)
  - [Guardrails & Safety](#guardrails--safety)
  - [Observability](#observability)
- [E-Commerce API Use Cases](#e-commerce-api-use-cases)
- [Tech Stack & Libraries](#tech-stack--libraries)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Environment Variables](#environment-variables)
- [LangGraph Studio](#langgraph-studio)
- [Roadmap](#roadmap)

---

## Overview

This project combines two subsystems:

| Subsystem | Purpose | Entry Point |
|-----------|---------|-------------|
| **FastAPI Backend** | REST APIs for e-commerce domain (CRUD, auth, cart, orders) | `main.py` |
| **AI Shopping Assistant** | Conversational agent for product search, cart management, and policy Q&A | `src/streamlit_ai/streamlit_app.py` or LangGraph Studio |

The AI agent follows the **ReAct (Reasoning + Acting)** pattern: the LLM decides whether to call a tool (search products, add to cart, get cart) or respond directly. Tool calls are wired to the same FastAPI controllers used by the REST layer, so business logic stays consistent.

---

## System Architecture

```mermaid
flowchart TB
    subgraph UI["User Interfaces"]
        ST[Streamlit Chat UI]
        LGS[LangGraph Studio]
        API[FastAPI REST Clients]
    end

    subgraph AI["AI Layer — src/ai_manager/"]
        GO[Graph Orchestrator<br/>LangGraph StateGraph]
        AM[AI Manager<br/>LLM + Tools + Config]
        GR[NeMo Guardrails]
        RAG[RAG Node<br/>PGVector + Cohere Rerank]
        MEM[mem0 Long-term Memory]
        CP[Postgres Checkpointer]
    end

    subgraph Backend["FastAPI Backend — src/"]
        CUST[Customers]
        CAT[Category]
        PROD[Products]
        CART[Cart]
        ORD[Order]
    end

    subgraph Infra["Infrastructure"]
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        ES[(Elasticsearch)]
        RMQ[RabbitMQ]
        OLLAMA[Ollama<br/>llama3.1:8b]
        GROQ[Groq API<br/>Guardrail LLM]
        COHERE[Cohere API<br/>Reranker]
    end

    ST --> GO
    LGS --> GO
    GO --> AM
    GO --> GR
    GO --> RAG
    GO --> MEM
    GO --> CP

    AM --> OLLAMA
    GR --> GROQ
    RAG --> COHERE
    RAG --> PG
    MEM --> PG
    CP --> PG

    GO -->|Tool calls| PROD
    GO -->|Tool calls| CART

    API --> CUST & CAT & PROD & CART & ORD
    CUST & CAT & PROD & CART & ORD --> PG
    PROD --> ES
    PROD --> REDIS
    PROD --> RMQ
    RMQ --> PG
```

---

## AI Shopping Assistant

### Design Pattern

| Pattern | Implementation |
|---------|----------------|
| **ReAct** | LLM reasons about user intent → calls tools when needed → synthesizes final answer |
| **State Machine** | LangGraph `StateGraph` with conditional edges between nodes |
| **Tool Calling** | LangChain `@tool` decorators bound to `llama3.1:8b` via Ollama |
| **RAG** | Retrieval-Augmented Generation for return/refund policy questions |
| **Guardrails** | NeMo Guardrails (Colang) + Groq safeguard model for off-topic filtering |
| **Stateful Chat** | Postgres checkpointer + in-memory product/cart state across turns |

### LangGraph Workflow

The graph is defined in `src/ai_manager/graph_orchestrator.py` and compiled with a Postgres checkpointer and in-memory node cache.

```mermaid
flowchart TD
    START([User Message]) --> RAILS[Guardrails Node<br/>NeMo Guardrails + Groq]

    RAILS -->|blocked| END_BLOCKED([Off-topic Response → END])
    RAILS -->|allowed| INTENT[Intent Router<br/>Keyword-based routing]

    INTENT -->|product_info| PMR[Product Memory Router]
    INTENT -->|add_to_cart| AGENT[Agent Node<br/>LLM + Tools]
    INTENT -->|get cart details| AGENT
    INTENT -->|general| AGENT
    INTENT -->|memory_write| MEM_WRITE[Memory Write Node<br/>mem0]
    INTENT -->|rag_node| RAG[RAG Node<br/>Policy Retrieval]

    PMR -->|memory_hit / memory_miss| AGENT

    MEM_WRITE --> AGENT
    RAG --> AGENT

    AGENT -->|tool_calls| TOOLS[Custom Tool Node]
    AGENT -->|no tools| END_OK([Final Response → END])

    TOOLS -->|search empty| NOT_FOUND[Product Not Found Node]
    TOOLS -->|has results| AGENT

    NOT_FOUND --> END_NF([Not Found Message → END])

    subgraph Tools["Available Tools"]
        T1[search_product]
        T2[add_product_to_cart]
        T3[get_cart]
    end

    TOOLS -.-> T1 & T2 & T3
```

#### Graph Nodes

| Node | File | Responsibility |
|------|------|----------------|
| `rails` | `graph_orchestrator.py` | Runs NeMo Guardrails on user input; blocks off-topic queries with `[OFF_TOPIC]` tag |
| `intent_router` | `graph_orchestrator.py` | Routes by keywords: product info, cart, memory write, policy/RAG, or general |
| `product_memory_router` | `graph_orchestrator.py` | Checks if a previously searched product exists in session memory |
| `agent` | `graph_orchestrator.py` | Builds dynamic system prompt with context; invokes LLM (with or without tools) |
| `tools` | `graph_orchestrator.py` | Executes tool calls; updates `search_results`, `product_memory`, `cart` in state |
| `product_not_found` | `graph_orchestrator.py` | Returns a friendly message when search returns no products |
| `memory_write` | `graph_orchestrator.py` | Persists user preferences to mem0 vector store |
| `rag_node` | `graph_orchestrator.py` | Full RAG pipeline for return/refund/policy questions |

### Intent Routing

Keyword-based routing in `route_intent()`:

| Intent | Trigger Keywords | Route |
|--------|-----------------|-------|
| `product_info` | price, availability, available, stock, quantity | → Product Memory Router → Agent |
| `add_to_cart` | add to cart, add | → Agent (with tools) |
| `get cart details` | cart, cart details | → Agent (with tools) |
| `memory_write` | remember, preference, save, preferred, store | → mem0 Memory Write → Agent |
| `rag_node` | refund, return, policy, terms and condition | → RAG Node → Agent |
| `general` | everything else | → Agent |

### RAG Pipeline

Policy documents (return/refund) are stored in **PGVector** and retrieved when users ask policy-related questions.

```mermaid
flowchart LR
    Q[User Query] --> RW[Query Rewriting<br/>Ollama llama3.1:8b]
    RW --> CACHE{Redis Semantic<br/>Cache Hit?}

    CACHE -->|HIT| CTX[Retrieved Context]
    CACHE -->|MISS| VS[PGVector Similarity Search<br/>HuggingFace all-MiniLM-L6-v2<br/>k=10, score ≥ 0.2]

    VS --> FILTER[Filter by Relevance Score]
    FILTER --> RR[Cohere Rerank<br/>rerank-english-v3.0<br/>threshold ≥ 0.05]
    RR --> CTX
    CTX --> STORE[Cache Result<br/>Redis Semantic Cache TTL=3600s]
    STORE --> AGENT[Agent Node<br/>LLM generates answer from context]
```

**RAG components** (`src/ai_manager/db_manager.py`, `src/ai_manager/utils.py`):

| Step | Technology | Details |
|------|-----------|---------|
| Query rewriting | Ollama `llama3.1:8b` | Resolves pronouns, normalizes policy terminology using conversation history |
| Vector store | PGVector + `all-MiniLM-L6-v2` | Collection: `refund/return policy` |
| Semantic cache | `langchain-redis` `RedisSemanticCache` | Skips vector search + rerank on similar queries |
| Reranking | Cohere `rerank-english-v3.0` | Top-3 documents, relevance threshold 0.05 |
| Pipeline versioning | SHA-256 hash of config | Cache invalidation when RAG params change |

### Agent Tools

Tools are defined in `src/ai_manager/tools.py` and wrap existing FastAPI controllers:

| Tool | Backend | Description |
|------|---------|-------------|
| `search_product` | `ProductController.search_product_by_name` | Fuzzy search via Elasticsearch → hydrate from PostgreSQL; populates `product_memory` |
| `add_product_to_cart` | Direct DB via `CartModel` / `CartItemModel` | Adds product from memory to cart; returns cart summary with total bill |
| `get_cart` | `CartController.get_cart_for_checkout` | Returns latest cart items with product details |
| `human_assistance` | LangGraph `interrupt` | Human-in-the-loop placeholder (not yet wired in graph) |

### State & Memory

**LangGraph State** (`State` TypedDict in `graph_orchestrator.py`):

```
messages, mobile, location, search_results, cart, product_memory,
cart_details, search_completed, guardrail_blocked, requested_product,
retrieved_context, retrieved_documents, memory_results
```

| Memory Type | Storage | Purpose |
|-------------|---------|---------|
| **Conversation checkpoint** | Postgres (`PostgresSaver`) | Persists full graph state per `thread_id` (customer ID) |
| **Product memory** | In-graph state (`product_memory` dict) | Caches searched products within a session to avoid re-searching |
| **Long-term user memory** | mem0 + ChromaDB | Stores user preferences ("remember I prefer organic") |
| **RAG cache** | Redis semantic cache | Caches retrieved policy context for similar queries |
| **Node cache** | LangGraph `InMemoryCache` | 240s TTL on tool node executions |

### Guardrails & Safety

Two layers of input safety:

1. **NeMo Guardrails** (`src/ai_manager/rails/`)
   - Colang flows for off-topic detection
   - Groq `llama-3.3-70b-versatile` as guardrail LLM
   - Blocks non-shopping queries before they reach the agent

2. **System prompt guard** (`src/ai_manager/prompt.py`)
   - Instructs LLM to tag off-topic responses with `[OFF_TOPIC]`

### Observability

| Tool | Purpose |
|------|---------|
| **LangSmith** | Traces all graph nodes (`@traceable`), project: `ecom-Agent_latest_v2` |
| **MetricCallBacks** | Custom callback handler logging token usage, cost estimates, tool calls |
| **Streamlit Debug Panel** | Real-time view of graph state, tool requests/responses, node timings, checkpoint history |

---

## E-Commerce API Use Cases

### Customers (`/customers`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/customers/create` | Create a new customer profile |
| GET | `/customers/all` | List all customers |
| GET | `/customers/{customer_id}` | Get customer by ID |
| POST | `/customers/register` | Register credentials (password) for existing customer |
| POST | `/customers/login` | Login → JWT access token + refresh token |
| GET | `/customers/is_auth` | Validate authentication headers |

### Category (`/category`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/category/create` | Create a product category |
| GET | `/category/all` | List all categories |
| GET | `/category/{id}` | Get category by ID and code |

### Products (`/products`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/products/{category_id}/add` | Add a product to a category |
| POST | `/products/{category_id}/bulk-add` | Bulk upload products via CSV (queued to RabbitMQ) |
| GET | `/products/all` | List products (paginated by `limit`) |
| GET | `/products/{product_id}` | Get product by ID (Redis cache, 60s TTL) |
| PATCH | `/products/{product_id}` | Update a product |
| GET | `/products?name=...` | Fuzzy search by name (Elasticsearch + PostgreSQL, auth required) |

### Cart (`/cart`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cart/get?location=...` | Create/get a cart for authenticated customer |
| POST | `/cart/{cart_id}/products/add` | Add product to cart |
| POST | `/cart/{cart_id}/delivery/add-address` | Add delivery address (pincode 560001–560114) |

### Orders (`/order`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/order/create` | Create order from cart (requires delivery address) |
| GET | `/order/order-details?order_id=...` | Get order details with line items |

### Async Processing

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant RMQ as RabbitMQ
    participant Consumer
    participant DB as PostgreSQL

    Client->>API: POST /products/{id}/bulk-add (CSV)
    API->>RMQ: Publish each product row
    API-->>Client: queued_count + errors

    Consumer->>RMQ: Consume messages
    Consumer->>DB: Insert ProductModel rows
```

Run the consumer separately: `python -m src.utils.consumer`

---

## Tech Stack & Libraries

### Core Backend

| Library | Role |
|---------|------|
| `fastapi[standard]` | REST API framework |
| `pydantic` / `pydantic-settings` | Request/response validation, `.env` config |
| `SQLAlchemy` | ORM for PostgreSQL |
| `redis` | Async caching (product lookup, login rate limiting, RAG semantic cache) |
| `aio-pika` | RabbitMQ async client for bulk product upload |
| `elasticsearch` | Fuzzy product name search |
| `pytest` / `pytest-mock` | Unit testing |

### AI / Agent Layer

| Library | Role |
|---------|------|
| `langgraph` | State graph orchestration, checkpointing, caching |
| `langchain` / `langchain-core` / `langchain-community` | LLM abstractions, prompts, tools |
| `langchain-ollama` | Ollama integration (`llama3.1:8b`) |
| `langchain-groq` | Groq API for guardrail LLM |
| `langchain_postgres` | PGVector store for RAG documents |
| `langchain_huggingface` | `all-MiniLM-L6-v2` embeddings |
| `langchain-redis` | Redis semantic cache for RAG |
| `langgraph-checkpoint-postgres` | Postgres conversation persistence |
| `nemoguardrails` | Input guardrails (Colang flows) |
| `mem0ai` | Long-term user preference memory (ChromaDB backend) |
| `cohere` | Document reranking (`rerank-english-v3.0`) |
| `chromadb` | Vector store for mem0 |
| `sentence-transformers` | Embedding models |
| `pypdf` / `unstructured[pdf]` | PDF ingestion for policy documents |
| `faiss-cpu` | Vector search (available, used in experiments) |
| `deepeval` | LLM evaluation framework (artifacts in `.deepeval/`) |
| `langgraph-cli[inmem]` | LangGraph Studio local dev server |

### UI

| Library | Role |
|---------|------|
| `streamlit` | Chat UI with debug panel for the shopping assistant |

### External Services

| Service | Default URL | Used By |
|---------|-------------|---------|
| Ollama | `http://localhost:11434` | Main chat LLM (`llama3.1:8b`) |
| Groq API | Cloud | Guardrail LLM |
| Cohere API | Cloud | RAG reranking |
| PostgreSQL | `.env` `DB_CONNECTION` | App DB + RAG vectors + checkpointer |
| Redis | `.env` `REDIS_URL` | Product cache, RAG cache, rate limiting |
| Elasticsearch | `http://localhost:9200` | Product fuzzy search |
| RabbitMQ | `amqp://guest:guest@localhost/` | Bulk product upload queue |
| LangSmith | Cloud | Tracing and observability |

---

## Project Structure

```
Fast_API/
├── main.py                          # FastAPI entry point
├── requirement.txt                  # Python dependencies
├── pyproject.toml                   # LangGraph Studio package config
├── langgraph.json                   # LangGraph Studio graph definition
├── README.md                        # This file
├── README.txt                       # Original technical design document
│
├── src/
│   ├── customers/                   # Customer CRUD, auth (JWT)
│   ├── category/                    # Product categories
│   ├── products/                    # Products, ES search, bulk upload
│   ├── cart/                        # Cart management, delivery address
│   ├── order/                       # Order creation and details
│   │
│   ├── ai_manager/                  # ★ AI Shopping Assistant
│   │   ├── ai_manager.py            # LLM init, tools binding, config
│   │   ├── graph_orchestrator.py    # LangGraph StateGraph definition
│   │   ├── tools.py                 # LangChain tools (search, cart)
│   │   ├── db_manager.py            # PGVector, mem0, RAG cache, query rewrite
│   │   ├── utils.py                 # Cohere rerank, pipeline versioning
│   │   ├── prompt.py                # System prompts
│   │   ├── callbacks.py             # Token/cost metric callbacks
│   │   ├── mem0_config.py           # mem0 ChromaDB configuration
│   │   ├── dtos.py                  # Tool response schemas
│   │   └── rails/                   # NeMo Guardrails (Colang + config)
│   │       ├── config.yml
│   │       └── guardrails.co
│   │
│   ├── streamlit_ai/                # Streamlit chat UI
│   │   └── streamlit_app.py
│   │
│   └── utils/
│       ├── db.py                    # SQLAlchemy engine & session
│       ├── settings.py              # pydantic-settings
│       ├── redis.py                 # Async Redis client
│       ├── rabbitmq.py              # RabbitMQ publisher
│       ├── consumer.py              # RabbitMQ consumer (standalone)
│       ├── es_client.py             # Elasticsearch client
│       ├── es_add_product.py        # ES index population script
│       └── helper.py                # Password hashing, cart ID, rate limiting
│
├── tests/
│   ├── conftest.py
│   └── test_customer.py
│
├── docs/                            # Sample data (CSV, policy PDFs)
├── chroma_db/                       # ChromaDB storage
└── data/mem0-chroma_db/             # mem0 vector store
```

---

## Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Elasticsearch 8.x
- RabbitMQ
- [Ollama](https://ollama.com/) with `llama3.1:8b` pulled
- API keys: `GROQ_API_KEY`, `COHERE_API_KEY` (optional: LangSmith)

---

## Installation

```bash
# Clone and enter project
cd Fast_API

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirement.txt

# Pull Ollama model
ollama pull llama3.1:8b
```

---

## Running the Application

### 1. FastAPI Backend

```bash
fastapi dev main.py --reload
```

API docs: `http://127.0.0.1:8000/docs`

### 2. AI Shopping Assistant (Streamlit)

```bash
python -m streamlit run src/streamlit_ai/streamlit_app.py
```

### 3. RabbitMQ Consumer (for bulk product upload)

```bash
python -m src.utils.consumer
```

### 4. Elasticsearch Index Setup

```bash
python -m src.utils.es_add_product
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DB_CONNECTION=postgresql://user:password@localhost:5432/ecom
RAG_DB_URL=postgresql+psycopg://user:password@localhost:5432/rag_db

# Auth
SECRET_KEY=your-secret-key
ALGORITHM=HS256
EXP_TIME=30

# Redis
REDIS_URL=redis://localhost:6379

# AI Services
GROQ_API_KEY=your-groq-api-key
COHERE_API_KEY=your-cohere-api-key

# Rate Limiting
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCKOUT_MINUTES=15
```

---

## LangGraph Studio

The graph is exportable for visual debugging in LangGraph Studio:

```bash
langgraph dev
```

Configuration in `langgraph.json`:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/ai_manager/graph_orchestrator.py:get_graph"
  },
  "env": ".env"
}
```

---

## Roadmap

Planned enhancements (from project notes):

- [ ] WebSocket endpoint for real-time agent chat via FastAPI
- [ ] Order placement and cancellation tools for the agent
- [ ] Delivery address tool and order status tracking
- [ ] Human-in-the-loop approval for place/cancel order
- [ ] Remove product from cart (API + tool)
- [ ] Order placement notifications / webhooks
- [ ] deepeval evaluation pipeline (RAG metrics, tool call metrics, GEval)
- [ ] Self-RAG and Adaptive RAG
- [ ] Retry strategies and LLM fallbacks
- [ ] Production deployment with Kubernetes
- [ ] Alembic database migrations
- [ ] Centralized auth via FastAPI `Depends`

---

## License

Private project — not licensed for public distribution.
