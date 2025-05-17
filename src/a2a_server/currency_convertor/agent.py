import os
from collections.abc import AsyncIterable
from typing import Any, Literal

import httpx
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

memory = MemorySaver()


def get_api_key() -> str:
    """Helper method to handle API Key."""
    load_dotenv()
    return os.getenv("GOOGLE_API_KEY")


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str


os.environ["LANGSMITH_TRACING"] = "true"


class CurrencyAgent:
    SYSTEM_INSTRUCTION = (
        "You are a specialized assistant for currency conversions. "
        "Your sole purpose is to use the 'get_exchange_rate' tool to answer questions about currency exchange rates. "
        "If the user asks about anything other than currency conversion or exchange rates, "
        "politely state that you cannot help with that topic and can only assist with currency-related queries. "
        "Do not attempt to answer unrelated questions or use tools for other purposes."
        "Set response status to input_required if the user needs to provide more information."
        "Set response status to error if there is an error while processing the request."
        "Set response status to completed if the request is complete."
    )

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite")

    async def invoke(self, query, sessionId) -> str:
        async with MultiServerMCPClient(
            {
                "currency": {
                    "command": "python",
                    "args": [
                        "/Users/kirushikeshdb/Documents/Personal Projects/A2A_MCP/a2a_mcp/src/mcp_server/server.py"
                    ],
                    "transport": "stdio",
                }
            }
        ) as client:
            self.graph = create_react_agent(
                self.model,
                tools=client.get_tools(),
                checkpointer=memory,
                prompt=self.SYSTEM_INSTRUCTION,
                response_format=ResponseFormat,
            )

            config = {"configurable": {"thread_id": sessionId}}
            await self.graph.ainvoke({"messages": [("user", query)]}, config)
            return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[dict[str, Any]]:
        async with MultiServerMCPClient(
            {
                "currency": {
                    "command": "python",
                    "args": [
                        "/Users/kirushikeshdb/Documents/Personal Projects/A2A_MCP/a2a_mcp/src/mcp_server/server.py"
                    ],
                    "transport": "stdio",
                }
            }
        ) as client:
            self.graph = create_react_agent(
                self.model,
                tools=client.get_tools(),
                checkpointer=memory,
                prompt=self.SYSTEM_INSTRUCTION,
                response_format=ResponseFormat,
            )

            inputs = {"messages": [("user", query)]}
            config = {"configurable": {"thread_id": sessionId}}

            async for item in self.graph.astream(inputs, config, stream_mode="values"):
                message = item["messages"][-1]
                if (
                    isinstance(message, AIMessage)
                    and message.tool_calls
                    and len(message.tool_calls) > 0
                ):
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": "Looking up the exchange rates...",
                    }
                elif isinstance(message, ToolMessage):
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": "Processing the exchange rates..",
                    }

            yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get("structured_response")
        if structured_response and isinstance(structured_response, ResponseFormat):
            if (
                structured_response.status == "input_required"
                or structured_response.status == "error"
            ):
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message,
                }
            if structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.message,
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]
