from collections.abc import AsyncIterable
from typing import Any
import os
import uuid

from langchain_core.messages import AIMessage, ToolMessage

from langgraph.checkpoint.memory import MemorySaver
from components.graph import builder
from components.struct import ResponseFormat

memory = MemorySaver()

os.environ["LANGSMITH_TRACING"] = "true"

class DeepResearchAgent:

    def __init__(self):
        self.graph = builder.compile(checkpointer=memory)

    def invoke(self, query, sessionId) -> str:
        config = {
            "configurable": {
                "thread_id": sessionId,
                "max_queries": 2,
                "search_depth": 2,
                "num_reflections": 2,
                "temperature": 0.7
            }
        }

        self.graph.invoke({'messages': [('user', query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[dict[str, Any]]:
        inputs = {'messages': [('user', query)]}
        config = {
            "configurable": {
                "thread_id": sessionId,
                "max_queries": 2,
                "search_depth": 2,
                "num_reflections": 2,
                "temperature": 0.7
            }
        }

        for item in self.graph.stream(inputs, config, stream_mode='values'):
            message = item['messages'][-1]
            if (
                isinstance(message, AIMessage)
                and message.tool_calls
                and len(message.tool_calls) > 0
            ):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Looking up the exchange rates...',
                }
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': 'Processing the exchange rates..',
                }

        yield self.get_agent_response(config)

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get('structured_response')
    
        if structured_response and isinstance(
            structured_response, ResponseFormat
        ):
            if (
                structured_response.status == 'input_required'
                or structured_response.status == 'error'
            ):
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }

        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': 'We are unable to process your request at the moment. Please try again.',
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']