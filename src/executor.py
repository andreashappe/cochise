import asyncio
import datetime
import pathlib
import litellm

from jinja2 import Template
from dataclasses import dataclass
from typing import Callable

from langchain_core.prompts import PromptTemplate

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn,TimeElapsedColumn

from common import Task, is_tool_call

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PROMPT = PromptTemplate.from_file(str(TEMPLATE_DIR / 'executor_prompt.md.jinja2'), template_format='jinja2')


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

    def get_function(self, str) -> Callable:
        return self.mapping[str]


def tool_calls_to_json(tool_calls):
    result = []
    if tool_calls is not None:
        for i in tool_calls:
            result.append({"name": i.function.name, "arguments": i.function.arguments})
    return result

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

@dataclass
class ToolResult:
    tool: str
    cmd: str
    finished: bool
    result: str

async def perform_tool_call(tool_call, tool):

    tool_msg = await tool.ainvoke(tool_call)
    cmd = tool_call["args"]["command"]

    return tool_msg, {
        'tool': tool_call['name'],
        'cmd': cmd,
        'finished': True,
        'result': tool_msg.content
    }


TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PROMPT = (TEMPLATE_DIR / "executor_prompt.md.jinja2").read_text()

async def executor_run(SCENARIO, task: Task, knowledge, model, api_key, tools, console, logger, MAX_ROUNDS:int=10):

    prompt = Template(PROMPT).render({
        'task': task,
        'max': str(MAX_ROUNDS-1),
        'knowledge': knowledge
    })
        
    history = [
        { "role": "system", "content": SCENARIO },
        { "role": "user", "content": prompt }
    ]

    tools = LLMFunctionMapping(tools)

    # try to solve our sub-task
    round = 1
    summary = None
    console.log("Starting low-level executor run..")
    while round <= MAX_ROUNDS:

        with console.status("[bold green]executor: thinking") as status:
            tik = datetime.datetime.now()

            print(model)
            print(api_key)

            response_message = llm_tool_call(
                model,
                api_key,
                tools,
                history
            )
            
            history.append(response_message)

            print(str(response_message))

        raise "does not work yet!!!"
        messages.append(ai_msg)

        metadata = ai_msg.response_metadata
        if hasattr(ai_msg, 'usage_metadata'):
            metadata['usage_metadata'] = ai_msg.usage_metadata


        logger.write_llm_call('executor_next_cmds', prompt='',
                              result={
                                'content': ai_msg.content,
                                'tool_calls': ai_msg.tool_calls
                              },
                              costs=metadata,
                              duration=(tok-tik).total_seconds())

        console.log(str(metadata))

        if is_tool_call(ai_msg):

            # output a summary before we do the acutal tool calls
            result = "\n\n".join(list(map(lambda x: f"{x['name']} ({x['args']['mitre_attack_technique']}/{x['args']['mitre_attack_procedure']}):\n{x['args']['command']}", ai_msg.tool_calls)))
            console.print(Panel(result, title="Tool Call(s)"))

            tasks = []
            display = {}

            with Progress(SpinnerColumn(),
                          TextColumn("[progress.description]{task.description}"),
                          BarColumn(),
                          TimeElapsedColumn(),
                          console=console
                          ) as progress:
                for tool_call in ai_msg.tool_calls:
                    display[tool_call['id']] = progress.add_task(f"[bold green]Executing `{tool_call['args']['command']}`", total=100)
                    tasks.append(asyncio.create_task(perform_tool_call(tool_call, mapping[tool_call["name"]])))

                for done in asyncio.as_completed(tasks):
                    tool_msg, result = await done
                    task_id = display[tool_msg.tool_call_id]
                    progress.update(task_id, advance=100)
                    progress.console.print(Panel(tool_msg.content, title=f"Tool Result for {result['cmd']}"), markup=False)
                    logger.write_executor_tool_call('executor_cmd', result['cmd'], '?', tool_msg.content)
                    messages.append(tool_msg)
        else:
            # the AI message has not tool_call -> this was some sort of result then

            if ai_msg.content == '':
                console.log(str(ai_msg))
                console.log("Empty response from executor LLM.. retrying")
            else:
                # workaround for gemini output
                try:
                    if 'type' in ai_msg.content[0] and ai_msg.content[0]['type'] == 'text':
                        summary = ai_msg.content[0]['text']
                    else:
                        summary = ai_msg.content
                    break
                except Exception as e:
                    console.log(str(ai_msg))
                    print(str(e))
                    raise e

        round = round + 1

    return summary, messages
