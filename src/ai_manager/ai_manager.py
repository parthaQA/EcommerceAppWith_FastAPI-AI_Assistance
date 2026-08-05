import json
import os
import time
from pathlib import Path
from typing import Annotated
import asyncio

from dotenv import load_dotenv
from langchain_core.tracers import LangChainTracer
from langgraph.types import Command
from langsmith import traceable
from psycopg_pool import ConnectionPool
from typing_extensions import TypedDict
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.ai_manager.callbacks import MetricCallBacks
from src.ai_manager.prompt import PRODUCT_SEARCH_SYSTEM_PROMPT
from src.ai_manager.tools import Tools
from src.customers.controller import CustomerController
from src.customers.dtos import CustomerLoginSchema
from src.utils.db import Local_Session
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from uuid import uuid4

from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig

from langchain_groq import ChatGroq


load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

guardrail_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=str(groq_api_key),
    temperature=0,
)
GUARDRAILS_DIR = Path(__file__).parent / "rails"

def get_rails_config():
    config = RailsConfig.from_path(str(GUARDRAILS_DIR))

    rails = LLMRails(config=config, llm=guardrail_llm)

    return rails


# -------------------------------------------------------
# Login & Initialization
# -------------------------------------------------------
customer_controller = CustomerController()
db = Local_Session()

login_response = asyncio.run(
    customer_controller.customer_login_internal(
        body=CustomerLoginSchema(
            mobile=8981137640,
            password="uwsb#1234"
        ),
        db=db
    )
)

class State(TypedDict):

    messages: Annotated[list, add_messages]


    mobile: str


    location: str

    search_results: list[dict]

    cart: dict

    product_memory: dict

    cart_details: dict

    search_completed: bool

    guardrail_blocked: bool



langsmith = LangChainTracer(
    project_name="Shopping-Agent"
)

config = {
    "tags": [
        "shopping",
        "search"
    ],
    "run_id": uuid4(),
    "callbacks": [ MetricCallBacks(), langsmith],
    "configurable": {
        "thread_id": login_response.get("customer_id") + "1",
        "user": {
            "access_token": login_response.get("access_token"),
            "customer_id": login_response.get("customer_id"),
            "refresh_token": login_response.get("refresh_token"),
            "mobile": login_response.get("mobile"),
        }
    }
}






from urllib.parse import quote_plus

password = quote_plus("asdf#1234")

DATABASE_URL = (
    f"postgresql://postgres:{password}@localhost:5432/ecom"
)

pool = ConnectionPool(conninfo=DATABASE_URL,
                      kwargs={"autocommit": True},
                      )

checkpointer = PostgresSaver(pool)

checkpointer.setup()


llm_chat = init_chat_model(
    model="llama3.1:8b",
    model_provider="ollama",
    base_url="http://localhost:11434",
    streaming = True,
)


tools = [
    Tools.get_search_product_tool(customer_id=config["configurable"]["user"]["customer_id"], db=db),
    Tools.add_product_to_cart_llm(customer_id=config["configurable"]["user"]["customer_id"], db=db),
    Tools.get_cart_tool(db=db)

]

tools_by_name = {
    tool.name: tool
    for tool in tools
}

llm_with_tools = llm_chat.bind_tools(tools)



# -------------------------------------------------------
# Agent Node
# -------------------------------------------------------
@traceable
def guardrails_node(state: State):

    last_message = state["messages"][-1]
    # Get latest user message
    query = last_message.content

    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content
            break

    result = get_rails_config().generate(
        messages=[
            {
                "role": "user",
                "content": query
            }
        ]
    )

    from pprint import pprint

    print("type : ", type(result))
    print("response :", result)

    #
    # If Guardrails generated a reply,
    # stop the graph.
    #
    # Extract assistant response
    if isinstance(result, dict):
        assistant_reply = result["content"]
    else:
        assistant_reply = str(result)

    blocked = assistant_reply != ""

    if blocked:
        return {
            "messages": [
                AIMessage(content=assistant_reply)
            ],
            "guardrail_blocked": True,
        }

    return {
        "guardrail_blocked": False,
    }

@traceable
def guardrail_router(state: State):

    if state.get("guardrail_blocked"):
        return "blocked"

    return "allowed"

@traceable
def route_intent(state: State):
    start = time.perf_counter()
    query = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            query = msg.content.lower()
            break

    print(f"Intent Router : {query}")



    if any(word in query for word in [
        "price",
        "availability",
        "available",
        "stock",
        "quantity"
    ]):
        return "product_info"

    elif any(word in query for word in [
        "cart",
        "add",
    ]):
        return "add_to_cart"

    elif any(word in query for word in [
        "cart", "cart details"
    ]):
        return "get cart details"

    print(f"route_intent {time.perf_counter() - start:.2f}s")

    return "general"



def product_memory_router_node(state: State):
    product_name = state["requested_product"]
    memory = state.get("product_memory", {})
    if product_name.lower() in memory:
        return "memory_found"

    return "memory_not_found"

@traceable
def route_product_memory(state: State):

    question = state["messages"][-1].content.lower()

    product_memory = state.get("product_memory", {})

    print("\n========== PRODUCT MEMORY ROUTER ==========")
    print("Question :", question)
    print("Products in memory :", list(product_memory.keys()))

    # Check whether any stored product name appears in the question
    for product_name in product_memory.keys():

        if product_name.lower() in question:

            print(f"Memory HIT -> {product_name}")

            return "memory_hit"

    print("Memory MISS")

    return "memory_miss"


MAX_HISTORY = 1

@traceable
def build_chat_history(messages):
    """
    Keep only recent Human/AI conversation.
    Ignore ToolMessages and empty AI tool-call messages.
    """
    history = []

    for msg in messages:

        if isinstance(msg, (HumanMessage, ToolMessage)):
            history.append(msg)

        elif isinstance(msg, AIMessage):
            if msg.content.strip():
                history.append(msg)

    return history[-MAX_HISTORY:]

@traceable
def call_model(state: State):

    ########################################################
    # 1. Intent
    ########################################################

    intent = route_intent(state)
    print("intent of route:", intent)

    ########################################################
    # 2. Current question
    ########################################################

    question = ""

    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            question = msg.content.lower()
            break

    ########################################################
    # 3. Find matching product
    ########################################################

    matched_product = None

    for _, product in state.get("product_memory", {}).items():

        if product["name"].lower() in question:
            matched_product = product
            break

    ########################################################
    # 4. Select model
    ########################################################

    if intent == "product_info" and matched_product:
        model = llm_chat
    else:
        model = llm_with_tools

    ########################################################
    # 5. Build dynamic context
    ########################################################

    dynamic_context = []

    #
    # Priority 1 -> Latest search results
    #
    if state.get("search_results"):

        dynamic_context.append(
            f"""
Latest Search Results

{json.dumps(state["search_results"], indent=2)}

These are the latest search results.

Use ONLY these products.

Do not search again unless the user asks for a different product.
"""
        )

    #
    # Priority 2 -> Product memory (only when search results don't exist)
    #
    elif matched_product:

        dynamic_context.append(
            f"""
Current Product

{json.dumps(matched_product, indent=2)}

This product already exists in memory.

Reuse this information.

Do not search again.
"""
        )

    #
    # Cart context (only when required)
    #
    if intent in ("add_to_cart", "get cart details"):

        if state.get("cart"):

            dynamic_context.append(
                f"""
Current Cart

{json.dumps(state["cart"], indent=2)}
"""
            )

        if state.get("cart_details"):

            dynamic_context.append(
                f"""
Latest Cart Details

{json.dumps(state["cart_details"], indent=2)}
"""
            )

    ########################################################
    # 6. Keep only latest human message
    ########################################################

    history = []

    for msg in reversed(state["messages"]):

        if isinstance(msg, HumanMessage):
            history.append(msg)
            break

    history.reverse()

    ########################################################
    # 7. Build prompt
    ########################################################

    system_prompt = PRODUCT_SEARCH_SYSTEM_PROMPT

    if dynamic_context:
        system_prompt += "\n\n" + "\n\n".join(dynamic_context)

    messages = [
        SystemMessage(content=system_prompt),
        *build_chat_history(state["messages"]),
    ]

    ########################################################
    # 8. Prompt analysis
    ########################################################

    print("\n" + "=" * 80)
    print("PROMPT ANALYSIS")
    print("=" * 80)

    total_chars = 0

    for i, msg in enumerate(messages):

        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        total_chars += len(content)

        print(
            f"{i:02d} | "
            f"{type(msg).__name__:<15} | "
            f"{len(content):5d} chars | "
            f"{content[:120].replace(chr(10), ' ')}..."
        )

    print("=" * 80)
    print(f"Total Prompt Characters : {total_chars}")
    print("=" * 80)

    ########################################################
    # 9. Invoke model
    ########################################################
    # messages = trim_messages(
    #     messages,
    #     max_tokens=2000,
    #     token_counter=model,
    #     strategy="last",
    #     include_system=True,
    # )
    # print("trim message before llm invoke :", messages)

    response = model.invoke(messages)

    # print(f"Input Tokens : {response.usage_metadata['input_tokens']}")
    # print(f"Output Tokens: {response.usage_metadata['output_tokens']}")
    # print(f"Total Tokens : {response.usage_metadata['total_tokens']}")


    return {
        "messages": [response]
    }

@traceable
def custom_tool_node(state: State):

    last_ai = state["messages"][-1]

    outputs = []

    updates = {}

    for tool_call in last_ai.tool_calls:

        tool = tools_by_name[tool_call["name"]]

        tool_args = dict(tool_call["args"])

        # Inject graph state manually
        tool_args["state"] = state

        result = tool.invoke(tool_args)

        outputs.append(
            ToolMessage(
                content=json.dumps(result),
                tool_call_id=tool_call["id"],
                name=tool_call["name"]
            )
        )

        ###################################################
        # Save tool outputs into graph state
        ###################################################

        if tool_call["name"] == "search_product":

            updates["search_results"] = result["products"]
            updates["product_memory"] = result["product_memory"]
            updates["search_completed"] = True

        elif tool_call["name"] == "add_product_to_cart":

            updates["cart"] = result["data"]

        elif tool_call["name"] == "get_cart":

            updates["cart_details"] = result["data"]

    return {

        "messages": outputs,

        **updates
    }


@traceable
def after_tool_router(state: State):

    if (
        state.get("search_completed")
        and not state["search_results"]
    ):
        return "not_found"

    return "agent"

#####################################################
# Tools -> Agent
#####################################################
@traceable
def product_not_found_node(state: State):
    return {
        "messages": [
            AIMessage(
                content=(
                    "I couldn't find any matching products. "
                    "Would you like to search again?"
                )
            )
        ]
    }

@traceable
def intent_router_node(state: State):
    return state

graph = StateGraph(State)

# -----------------------------
# Add nodes FIRST
# -----------------------------

graph.add_node("rails", guardrails_node)

graph.add_node("intent_router", intent_router_node)

graph.add_node("product_memory_router", product_memory_router_node)

graph.add_node("agent", call_model)

graph.add_node("tools", custom_tool_node)

graph.add_node("product_not_found", product_not_found_node)

# -----------------------------
# Now connect them
# -----------------------------

graph.add_edge(
    START,
    "rails"
)

graph.add_conditional_edges(
    "rails",
    guardrail_router,
    {
        "blocked": END,
        "allowed": "intent_router",
    }
)

graph.add_conditional_edges(
    "intent_router",
    route_intent,
    {
        "product_info": "product_memory_router",
        "add_to_cart": "agent",
        "get cart details": "agent",
        "general": "agent",
    }
)

graph.add_conditional_edges(
    "product_memory_router",
    route_product_memory,
    {
        "memory_hit": "agent",
        "memory_miss": "agent",
    }
)

graph.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        "__end__": END,
    }
)

graph.add_conditional_edges(
    "tools",
    after_tool_router,
    {
        "agent": "agent",
        "not_found": "product_not_found",
    }
)

graph.add_edge(
    "product_not_found",
    END
)

graph_builder = graph.compile(checkpointer=checkpointer)


# -------------------------------------------------------
# Save graph image
# -------------------------------------------------------

png_data = graph_builder.get_graph().draw_mermaid_png()
Path("langgraph2.png").write_bytes(png_data)


# -------------------------------------------------------
# Interactive Chat
# -------------------------------------------------------
#
# print("=" * 60)
# print("Shopping Assistant")
# print("Type 'exit' to quit.")
# print("=" * 60)
#
# first_turn = True
#
# while True:
#
#     query = input("\nYou : ")
#
#     if query.lower() in ("exit", "quit"):
#         print("Goodbye!")
#         break
#
#     # -------------------------------------------------------
#     # Build state
#     # -------------------------------------------------------
#
#     if first_turn:
#
#         state = {
#             "messages": [
#                 HumanMessage(content=query)
#             ],
#             "customer_id": login_response["customer_id"],
#             "mobile": login_response["mobile"],
#             "access_token": login_response["access_token"],
#             "refresh_token": login_response["refresh_token"],
#             "location": "6.9270786%2C79.861243",
#             "product_memory": {}
#         }
#
#         first_turn = False
#
#     else:
#
#         state = {
#             "messages": [
#                 HumanMessage(content=query)
#             ]
#         }
#
#     # -------------------------------------------------------
#     # Execute Graph
#     # -------------------------------------------------------
#
#     assistant_response = ""
#
#     for event in graph_builder.stream(
#             state,
#             rails=rails,
#             stream_mode="updates"
#     ):
#
#         for node_name, node_output in event.items():
#
#             if "messages" not in node_output:
#                 continue
#
#             for msg in node_output["messages"]:
#
#                 if isinstance(msg, AIMessage):
#
#                     if not msg.tool_calls:
#                         assistant_response += msg.content
#
#
# st.session_state.chat_history.append(
#     {
#         "role": "assistant",
#         "content": assistant_response
#     }
# )
#
# for chat in st.session_state.chat_history:
#
#     with st.chat_message(chat["role"]):
#         st.markdown(chat["content"])