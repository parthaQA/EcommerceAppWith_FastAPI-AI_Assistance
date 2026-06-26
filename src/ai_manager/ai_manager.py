from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition

from src.ai_manager.prompt import PRODUCT_SEARCH_SYSTEM_PROMPT
from src.ai_manager.tools import Tools
from src.customers.controller import CustomerController
from src.customers.dtos import CustomerLoginSchema
from src.products.controller import ProductController
from IPython.display import display, Image
from pathlib import Path
from langchain_core.messages import SystemMessage
from src.products.dtos import ProductSchema
from src.utils.db import Local_Session
from fastapi import HTTPException, Request
from langgraph.prebuilt import InjectedState
from typing import Annotated
import asyncio

db = Local_Session()


customer_controller = CustomerController()

login_response = asyncio.run(customer_controller.customer_login_internal(
    body=CustomerLoginSchema(
        mobile=8981137640,
        password="uwsb#1234"
    ),
    db=db
)
)

llm_chat = init_chat_model(
    model="llama3.1:8b",
    model_provider="ollama",
    base_url="http://localhost:11434"
)

tools = [Tools.get_search_product_tool(db)]

llm_with_tools = llm_chat.bind_tools(tools)

initial_state = {
    "messages": [
        "search a product with name brocolli"
    ],

    "customer_id": login_response["customer_id"],

    "mobile": login_response["mobile"],

    "access_token": login_response["access_token"],

    "refresh_token": login_response["refresh_token"]
}

class State(TypedDict):
    messages: Annotated[list, add_messages]
    customer_id: int
    mobile: str
    access_token: str
    refresh_token: str



def call_model(state: State):
    messages = [
        SystemMessage(content=PRODUCT_SEARCH_SYSTEM_PROMPT),
        *state["messages"]
    ]
    print("\n=== CALL_MODEL EXECUTED ===")
    print(state["messages"])

    response = llm_with_tools.invoke(messages)
    print("\n=== LLM RESPONSE ===")
    print(response)
    return {"messages": [response]}

graph = StateGraph(State)

graph.add_node("agent", call_model)
graph.add_node("tools", ToolNode(tools))

graph.add_edge(START, "agent")

graph.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        "__end__": END,
    },
)

graph.add_edge("tools", "agent")

graph_builder = graph.compile()

for event in graph_builder.stream(initial_state):
    for value in event.values():
        print(value["messages"][-1].content)


png_data = graph_builder.get_graph().draw_mermaid_png()

Path("langgraph.png").write_bytes(png_data)

print("Graph saved as langgraph.png")

