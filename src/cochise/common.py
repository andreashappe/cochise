import datetime
import litellm
import os

from dataclasses import asdict
from typing import Any, Callable, Type
from pydantic import BaseModel

def get_or_fail(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"Environment variable {name} not set")
    return value

def is_tool_call(msg) -> bool:
    return hasattr(msg, "tool_calls") and msg.tool_calls is not None and len(msg.tool_calls) > 0

class LLMFunctionMapping:
    def __init__(self, tool_functions: list[Callable]):
        self.tools = []
        self.mapping = {}

        for i in tool_functions:
            tool = litellm.utils.function_to_dict(i)

            self.tools.append({"type": "function", "function": tool})
            self.mapping[tool["name"]] = i

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return self.tools

    def get_function(self, value) -> Callable:
        return self.mapping[value]
    
def convert_costs_to_json(costs):
    result = costs.__dict__
    if result["prompt_tokens_details"] is not None:
        result["prompt_tokens_details"] = costs.prompt_tokens_details.__dict__
    if result["completion_tokens_details"] is not None:
        result["completion_tokens_details"] = costs.completion_tokens_details.__dict__
    return result


def llm_tool_call(
    model: str,
    api_key: str,
    tools: LLMFunctionMapping,
    messages: list[dict[str, Any]]):

    tik = datetime.datetime.now()
    response = litellm.completion(
        model=model,
        messages=messages,
        tools=tools.get_tool_definitions(),
        api_key=api_key,
    )
    tok = datetime.datetime.now()

    if len(response.choices) != 1:
        raise RuntimeError(f"Expected exactly one LLM choice, but got {len(response.choices)}.")

    response_message = response.choices[0].message
    costs = convert_costs_to_json(response.usage)
    duration = (tok - tik).total_seconds()

    return response_message, costs, duration

def message_to_json(message):
    result = {"role": message.role}

    if message.content:
        result["content"] = message.content
    else:
        result["content"] = ""

    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return result

# only used by ptt for now, but could be used by executor in the future as well
def llm_typed_call[T: BaseModel](
    model: str,
    api_key: str,
    messages: list[dict[str, Any]],
    id: str,
    type: Type[T] | None = None,
) -> T:
    """make a simple LLM call without any response format parsing"""

    tik = datetime.datetime.now()
    response = litellm.completion(
        model=model,
        messages=messages,
        api_key=api_key,
        response_format=type,
    )
    tok = datetime.datetime.now()

    if len(response.choices) != 1:
        raise RuntimeError(f"Expected exactly one LLM choice, but got {len(response.choices)}.")

    # output tokens costs
    costs = convert_costs_to_json(response.usage)
    duration = (tok - tik).total_seconds()

    if type is not None:
        result = type.model_validate_json(response.choices[0].message.content)
        content = asdict(result)
        return result, duration, costs
    else:
        result = response.choices[0].message
        content = {
            "content": result.content,
            "reasoning_content": result.reasoning_content
            if hasattr(result, "reasoning_content")
            else None,
        }
        return content, duration, costs

