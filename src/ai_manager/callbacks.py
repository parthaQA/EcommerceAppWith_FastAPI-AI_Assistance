from typing import Any
from uuid import UUID

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import  BaseCallbackHandler
import time

from langchain_core.messages import BaseMessage
from langchain_core.outputs import GenerationChunk, ChatGenerationChunk, LLMResult
from langchain_protocol import MessagesData


class MetricCallBacks(BaseCallbackHandler):

    def __init__(self):
        self.start_time = None
        self.generated_text = ""
        self.end_time = None


    # def on_llm_start(
    #     self,
    #     serialized: dict[str, Any],
    #     prompts: list[str],
    #     *,
    #     run_id: UUID,
    #     parent_run_id: UUID | None = None,
    #     tags: list[str] | None = None,
    #     metadata: dict[str, Any] | None = None,
    #     **kwargs: Any,
    # ) -> Any:
    #
    #     self.start_time = time.perf_counter()
    #
    #     print("on llm start")
    #     print("=" * 80)
    #
    #     print("Model")
    #
    #     print(serialized)
    #
    #     print("=" * 80)
    #
    #     print("Prompt Count:", len(prompts))
    #
    #     print("=" * 80)
    #
    #     print("total prompt :", prompts)
    #
    #     print(prompts[0])
    #
    #     print("=" * 80)

    def on_llm_end(
            self,
            response: LLMResult,
            *,
            run_id: UUID,
            parent_run_id: UUID | None = None,
            **kwargs,
    ):
        duration = time.perf_counter() - self.start_time

        print("on_llm_end: ",response.generations[0][0])

        response_messages = response.generations[0][0]
        ai_message = response_messages.message

        INPUT_PRICE = 0.12 / 1_000_000
        OUTPUT_PRICE = 0.48 / 1_000_000


        print("----------------------------------------------------------")

        print("generation info: ", response_messages.generation_info)

        print("----------------------------------------------------------")

        print("ai message : ", ai_message.content)

        print("----------------------------------------------------------")

        print("response metadata : ", ai_message.response_metadata)

        print("----------------------------------------------------------")

        print("usage metadata :", ai_message.usage_metadata)

        print("----------------------------------------------------------")

        print("tool calls : ", ai_message.tool_calls)

        print("----------------------------------------------------------")

        print("input token :", ai_message.usage_metadata["input_tokens"])

        print("----------------------------------------------------------")

        print("output token :", ai_message.usage_metadata["output_tokens"])

        input_cost = ai_message.usage_metadata["input_tokens"] * INPUT_PRICE
        output_cost = ai_message.usage_metadata["output_tokens"] * OUTPUT_PRICE

        total_cost = input_cost + output_cost

        print("total cost:", total_cost)

        print(f"LLM Finished in {duration:.2f} seconds")


    def on_llm_new_token(
        self,
        token: str | list[str | dict[str, Any]],
        *,
        chunk: GenerationChunk | ChatGenerationChunk | None = None,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> Any:

        self.generated_text += str(token)

        print(f"Token :", self.generated_text, end="", flush=True)

        print("-" * 40)

        print("chunk info: ", chunk)


    def on_stream_event(
        self,
        event: MessagesData,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> Any:


        print("=" * 60)

        print("on stream event : ", event)

        print("=" * 60)


    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:

        print("on_tool_start")

        print("=" * 60)
        print("on tool start serialized :", serialized)

        print("=" * 60)

        print(input_str)
        print("=" * 60)


    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:

        print("on_tool_end")

        print("=" * 60)

        print("on tool end output : ", output)


    def on_agent_action(
        self,
        action: AgentAction,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:

        print("on_agent_action")

        print("=" * 60)

        print("agent action : ", action)


    def on_agent_finish(
        self,
        finish: AgentFinish,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:

        print("on_agent_finish")

        print("=" * 60)

        print("agent finish : ", finish)


    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:

        self.start_time = time.perf_counter()
        self.generated_text = ""

        print("on_chat_model_start")

        print("=" * 60)

        print("messages chat model: ", messages)