import asyncio
import sys
from pathlib import Path
from pprint import pprint

# streamlit_app.py

# Fast_API/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.customers.controller import CustomerController
from src.customers.dtos import CustomerLoginSchema
from src.utils.db import Local_Session
from src.ai_manager.ai_manager import graph_builder, login_response
from src.ai_manager.ai_manager import config
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage


class StreamlitShoppingAssistant:
    """
    Skeleton application.

    Replace the TODO sections with your existing graph code
    (call_model, custom_tool_node, graph_builder, etc.).
    """

    def __init__(self):
        st.set_page_config(layout="wide", page_title="Shopping Assistant")

        # -------------------------
        # Session Initialization
        # -------------------------

        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        if "first_turn" not in st.session_state:
            st.session_state.first_turn = True

        # 👇 ADD IT HERE
        if "debug" not in st.session_state:
            st.session_state.debug = {
                "graph_state": {},
                "events": [],
                "messages": [],
                "tool_requests": [],
                "tool_responses": [],
                "llm_responses": [],
                "timings": [],
                "history": [],
                "errors": [],
                "graph_execution_ms": 0
            }

        ss = st.session_state
        ss.setdefault("logged_in", False)
        ss.setdefault("chat_history", [])
        ss.setdefault("logs", [])
        ss.setdefault("state", {})
        ss.setdefault("events", [])
        ss.setdefault("tool_calls", [])
        ss.setdefault("usage", {})

    def sidebar(self):
        with st.sidebar:
            st.header("Configuration")
            st.selectbox("Model", ["llama3.1:8b"])
            st.slider("Temperature",0.0,1.0,0.5)
            st.text_input("Thread Id",login_response.get("customer_id"))
            if st.button("Clear Chat"):
                st.session_state.chat_history=[]
                st.rerun()

    def login(self):
        st.title("Shopping Assistant")
        col1, col2 = st.columns(2)

        mobile = col1.text_input(
            "Mobile Number",
            placeholder="8828162737"
        )

        otp = col2.text_input(
            "OTP",
            type="password",
            placeholder="Enter OTP"
        )
        customer_controller = CustomerController()
        db = Local_Session()
        if st.button("Login"):
            login_response = asyncio.run(
                customer_controller.customer_login_internal(
                    body=CustomerLoginSchema(
                        mobile=int(mobile),
                        password=otp  # OTP is passed here
                    ),
                    db=db
                )
            )

            st.session_state.logged_in = True

            st.session_state.customer_id = login_response["customer_id"]
            st.session_state.mobile = login_response["mobile"]
            st.session_state.access_token = login_response["access_token"]
            st.session_state.refresh_token = login_response["refresh_token"]

            st.session_state.state = {
                "customer_id": login_response["customer_id"],
                "mobile": login_response["mobile"],
                "access_token": login_response["access_token"],
                "refresh_token": login_response["refresh_token"],
                "location": "6.9270786%2C79.861243",
                "product_memory": {},
                "search_results": [],
                "cart": None,
            }

            st.success("Login Successful")
            st.rerun()

    def debug_panel(self):
        tabs=st.tabs(["State","Events","Tools","Logs","Tokens"])
        with tabs[0]:
            st.json(st.session_state.state)
        with tabs[1]:
            st.json(st.session_state.events)
        with tabs[2]:
            st.json(st.session_state.tool_calls)
        with tabs[3]:
            st.code("\n".join(st.session_state.logs))
        with tabs[4]:
            st.json(st.session_state.usage)

    def chat(self):

        import time

        left, right = st.columns([2, 1])

        # ==========================================================
        # LEFT PANEL - CHAT
        # ==========================================================

        with left:

            st.title("🛒 Shopping Assistant")

            # Previous Chat
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            query = st.chat_input("Ask me anything...")

            if query:

                st.session_state.chat_history.append({
                    "role": "user",
                    "content": query
                })

                with st.chat_message("user"):
                    st.markdown(query)

                ########################################################
                # Initial Graph State
                ########################################################

                if st.session_state.first_turn:

                    state = {
                        "messages": [HumanMessage(content=query)],
                        "customer_id": login_response["customer_id"],
                        "mobile": login_response["mobile"],
                        "access_token": login_response["access_token"],
                        "refresh_token": login_response["refresh_token"],
                        "location": "6.9270786%2C79.861243",
                        "product_memory": {},
                        "search_completed": False,
                    }

                    st.session_state.first_turn = False

                else:

                    state = {
                        "messages": [HumanMessage(content=query)]
                    }

                assistant_response = ""

                ########################################################
                # Clear previous debug
                ########################################################

                st.session_state.debug["events"] = []
                st.session_state.debug["messages"] = []
                st.session_state.debug["tool_requests"] = []
                st.session_state.debug["tool_responses"] = []
                st.session_state.debug["llm_responses"] = []
                st.session_state.debug["timings"] = []
                st.session_state.debug["history"] = []

                graph_start = time.perf_counter()

                ########################################################
                # Execute Graph
                ########################################################

                # for event in graph_builder.stream(
                #         state,
                #         rails=rails,
                #         stream_mode="updates"
                # ):
                #     print("\n" + "=" * 100)
                #     print("RAW EVENT")
                #     print("=" * 100)
                #     pprint(event)

                placeholder = st.empty()
                text = ""

                for mode, data in graph_builder.stream(
                        state,
                        config=config,
                        stream_mode=["messages", "updates"],
                ):

                    ####################################################
                    # Token streaming
                    ####################################################
                    if mode == "messages":
                        chunk, metadata = data

                        if chunk.content:
                            text += chunk.content
                            placeholder.markdown(text)

                    ####################################################
                    # Node updates
                    ####################################################
                    elif mode == "updates":

                        event = data

                        print("\n" + "=" * 80)
                        print("RAW EVENT")
                        print("=" * 80)
                        pprint(event)

                        for node_name, node_output in event.items():
                            print(f"\nNode: {node_name}")
                            print(f"Type: {type(node_output)}")
                            pprint(node_output)

                        node_start = time.perf_counter()

                        ####################################################
                        # Raw Event
                        ####################################################

                        st.session_state.debug["events"].append({
                            "node": node_name,
                            "output": node_output
                        })

                        ####################################################
                        # Current Graph State
                        ####################################################

                        try:

                            graph_state = graph_builder.get_state(config)

                            st.session_state.debug["graph_state"] = {
                                "values": graph_state.values,
                                "next": graph_state.next,
                                "metadata": graph_state.metadata
                            }

                        except Exception as e:

                            st.session_state.debug["errors"].append(str(e))

                        ####################################################
                        # Messages
                        ####################################################

                        if not node_output or "messages" not in node_output:
                            continue

                        for msg in node_output["messages"]:

                            st.session_state.debug["messages"].append({

                                "id": getattr(msg, "id", ""),

                                "node": node_name,

                                "type": type(msg).__name__,

                                "content": getattr(msg, "content", ""),

                                "tool_calls": getattr(msg, "tool_calls", None),

                                "usage": getattr(msg, "usage_metadata", None),

                                "metadata": getattr(msg, "response_metadata", None)

                            })

                            ################################################
                            # AI
                            ################################################

                            if isinstance(msg, AIMessage):

                                if msg.tool_calls:

                                    st.session_state.debug["tool_requests"].append({

                                        "node": node_name,

                                        "response_id": msg.id,

                                        "tool_calls": msg.tool_calls,

                                        "usage": getattr(
                                            msg,
                                            "usage_metadata",
                                            {}
                                        ),

                                        "metadata": getattr(
                                            msg,
                                            "response_metadata",
                                            {}
                                        )

                                    })

                                else:

                                    assistant_response = msg.content

                                    st.session_state.debug["llm_responses"].append({

                                        "node": node_name,

                                        "response_id": msg.id,

                                        "content": msg.content,

                                        "usage": getattr(
                                            msg,
                                            "usage_metadata",
                                            {}
                                        ),

                                        "metadata": getattr(
                                            msg,
                                            "response_metadata",
                                            {}
                                        )

                                    })

                            ################################################
                            # Tool Response
                            ################################################

                            elif isinstance(msg, ToolMessage):

                                st.session_state.debug["tool_responses"].append({

                                    "node": node_name,

                                    "tool_call_id": msg.tool_call_id,

                                    "tool_name": msg.name,

                                    "response": msg.content

                                })

                        ####################################################
                        # Node Timing
                        ####################################################

                        st.session_state.debug["timings"].append({

                            "node": node_name,

                            "time_ms": round(
                                (time.perf_counter() - node_start) * 1000,
                                2
                            )

                        })

                ########################################################
                # Total Graph Time
                ########################################################

                st.session_state.debug["graph_execution_ms"] = round(
                    (time.perf_counter() - graph_start) * 1000,
                    2
                )

                ########################################################
                # Checkpoint History
                ########################################################

                try:

                    for checkpoint in graph_builder.get_state_history(config):
                        st.session_state.debug["history"].append({

                            "values": checkpoint.values,

                            "next": checkpoint.next,

                            "metadata": checkpoint.metadata

                        })

                except Exception:
                    pass

                ########################################################
                # Final AI Response
                ########################################################

                with st.chat_message("assistant"):
                    st.markdown(assistant_response)

                st.session_state.chat_history.append({

                    "role": "assistant",

                    "content": assistant_response

                })

        # ==========================================================
        # RIGHT PANEL - DEBUG
        # ==========================================================

        with right:

            st.header("🐞 Debug")

            tabs = st.tabs([
                "State",
                "Messages",
                "Tools",
                "LLM",
                "Events",
                "Timing",
                "History"
            ])

            with tabs[0]:
                st.json(st.session_state.debug["graph_state"])

            with tabs[1]:
                st.json(st.session_state.debug["messages"])

            with tabs[2]:
                st.subheader("Tool Requests")
                st.json(st.session_state.debug["tool_requests"])

                st.subheader("Tool Responses")
                st.json(st.session_state.debug["tool_responses"])

            with tabs[3]:
                st.json(st.session_state.debug["llm_responses"])

            with tabs[4]:
                st.json(st.session_state.debug["events"])

            with tabs[5]:
                st.metric(
                    "Graph Execution",
                    f'{st.session_state.debug["graph_execution_ms"]} ms'
                )

                st.json(st.session_state.debug["timings"])

            with tabs[6]:
                st.json(st.session_state.debug["history"])


    def run(self):
        self.sidebar()
        if not st.session_state.logged_in:
            self.login()
        else:
            self.chat()

if __name__=="__main__":
    StreamlitShoppingAssistant().run()
