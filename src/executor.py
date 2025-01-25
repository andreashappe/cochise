import asyncio
from dataclasses import dataclass

from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn,TimeElapsedColumn

from ptt import ExecutedTask, Task

PROMPT = """
To achieve the scenario, focus upon the following task:
                                      
`{task.next_step}`
                                      
You are given the following additional information about the task:

```                                
{task.next_step_context}
```

Perform the task against the target environment. You have up to
{max} tries to achieve this, stop if you were not able to achieve this.

If you encounter errors, try to solve them.

If the task has been achieved or you reached the maximum allowed try count, stop the execution and state the key finding. Be concise but include the concrete findings that you can gather from the existing output. Include findings that are not directly related to your task too.
"""

def is_tool_call(msg) -> bool:
    return hasattr(msg, "tool_calls") and len(msg.tool_calls) > 0

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

async def executor_run(SCENARIO, task: Task, llm2_with_tools, tools, console, logger):

    # create a string -> tool mapping
    mapping = {}
    for tool in tools:
        mapping[tool.__class__.__name__] = tool

    # tool_call history
    history = []

    # how many rounds will we do?
    MAX_ROUNDS: int = 10

    # the initial prompt
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=SCENARIO),
            HumanMessagePromptTemplate.from_template(PROMPT)
        ]
    )

    # our message history
    messages = chat_template.format_messages(task=task, max=(MAX_ROUNDS-1))

    # try to solve our sub-task
    round = 1
    summary = None
    console.log("Starting low-level executor run..")
    while round <= MAX_ROUNDS:

        with console.status("[bold green]executor: thinking") as status:
            ai_msg = llm2_with_tools.invoke(messages)
        messages.append(ai_msg)

        console.print(Panel(str(ai_msg.response_metadata), title="Tool thinking: LLM costs"))
        logger.write_next_cmd_prompt(ai_msg)

        if is_tool_call(ai_msg):

            # output a summary before we do the acutal tool calls
            result = "\n".join(list(map(lambda x: f"{x['name']}: {x['args']['command']}", ai_msg.tool_calls)))
            console.print(Panel(result, title="Tool Call(s)"))
            logger.write_tool_calls(result)

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
                    logger.write_tool_result(result['cmd'], tool_msg.content)
                    history.append(result)
                    messages.append(tool_msg)
        else:
            # the AI message has not tool_call -> this was some sort of result then
            summary = ai_msg.content
            break
        round = round + 1

    # TODO: create a new summary if we were not able to achieve the task within $steps
    assert(summary != None)

    # output the result, then return it
    console.print(Panel(summary, title="ExecutorAgent Output"))
    logger.write_tool_summary(summary)

    console.log("Finished low-level executor run..")

    return ExecutedTask(task, summary, history)
