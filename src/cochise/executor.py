import asyncio
import json
import pathlib

from jinja2 import Template
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn,TimeElapsedColumn

from cochise.common import Task, is_tool_call, LLMFunctionMapping, llm_tool_call, message_to_json

def tool_calls_to_json(tool_calls):
    result = []
    if tool_calls is not None:
        for i in tool_calls:
            result.append({"name": i.function.name, "arguments": i.function.arguments})
    return result

async def perform_tool_call(id, tool_name, function, args):
    result = await function(**args)

    # todo: we could actually capture stdout/stderr separately here, as well as finished
    return {
        'tool': tool_name,
        'cmd': args['command'],
        'finished': True,
        'result': result,
        'tool_call_id': id
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
            response_message, costs, duration = llm_tool_call(
                model,
                api_key,
                tools,
                history
            )
            
            history.append(message_to_json(response_message))

        logger.write_llm_call('executor_next_cmds', prompt='',
                              result={
                                'content': response_message.content,
                                'tool_calls': response_message.tool_calls
                              },
                              costs=costs,
                              duration=duration)
        console.log(str(costs))

        if is_tool_call(response_message):

            tasks = []
            display = {}

            with Progress(SpinnerColumn(),
                          TextColumn("[progress.description]{task.description}"),
                          BarColumn(),
                          TimeElapsedColumn(),
                          console=console
                          ) as progress:
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    cmd = args['command']

                    display[tool_call.id] = progress.add_task(f"[bold green]Executing `{cmd}`", total=100)
                    tasks.append(asyncio.create_task(perform_tool_call(tool_call.id, function_name, tools.get_function(function_name), args)))

                for done in asyncio.as_completed(tasks):
                    result = await done

                    print(str(result))

                    task_id = display[result['tool_call_id']]
                    progress.update(task_id, advance=100)
                    progress.console.print(Panel(result['result'], title=f"Tool Result for {result['cmd']}"), markup=False)
                    logger.write_executor_tool_call('executor_cmd', result['cmd'], '?', result['result'])
                    history.append({
                        "tool_call_id": result['tool_call_id'],
                        "role": "tool",
                        "name": result['tool'],
                        "content": result['result'],
                    })
        else:
            # the AI message has not tool_call -> this was some sort of result then
            if response_message.content == '':
                console.log(str(response_message))
                console.log("Empty response from executor LLM.. retrying")
            else:
                summary = response_message.content
                break
        round = round + 1

    return summary, history
