import asyncio
import datetime
import pathlib

from dataclasses import dataclass
from typing import List

from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from rich.panel import Panel
from rich.pretty import Pretty
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn,TimeElapsedColumn

from ptt import ExecutedTask, Task, PostAnalysis

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PROMPT = PromptTemplate.from_file(str(TEMPLATE_DIR / 'executor_prompt.md.jinja2'), template_format='jinja2')

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

leads = []

async def executor_run(SCENARIO, task: Task, findings, llm2_with_tools, tools, console, logger):

    # create a string -> tool mapping
    mapping = {}
    for tool in tools:
        mapping[tool.__class__.__name__] = tool

    # tool_call history
    history = []

    # how many rounds will we do?
    MAX_ROUNDS: int = 10

    text = PROMPT.invoke(
            {'task': task,
                'max': str(MAX_ROUNDS-1),
                'findings': findings
            }).text
    
    print(str(text))

    # the initial prompt
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=SCENARIO),
            HumanMessagePromptTemplate.from_template(text)
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
            tik = datetime.datetime.now()
            ai_msg = llm2_with_tools.invoke(messages)
            tok = datetime.datetime.now()

        messages.append(ai_msg)

        logger.write_llm_call('executor_next_cmds', prompt='',
                              result={
                                'content': ai_msg.content,
                                'tool_calls': ai_msg.tool_calls
                              },
                              costs=ai_msg.response_metadata,
                              duration=(tok-tik).total_seconds())

        print(str(ai_msg.response_metadata))

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
                    logger.write_executor_tool_call('executor_cmd', result['cmd'], '?', tool_msg.content)
                    history.append(result)
                    messages.append(tool_msg)
        else:
            # the AI message has not tool_call -> this was some sort of result then
            summary = ai_msg.content
            break
        round = round + 1

    print(str(summary))

    # summarize the result and create the findings list
    #messages.append(HumanMessage(content="You ran into a timeout and cannot further explore your task. Plese provide a containing findings that arose while trying to solve the task"))
    #tik = datetime.datetime.now()
    #summary_msg = llm2_with_tools.invoke(messages)
    #tok = datetime.datetime.now()
    #logger.write_llm_call('executor_summary', prompt='',
    #                  result=summary_msg.content,
    #                  costs=summary_msg.response_metadata,
    #                  duration=(tok-tik).total_seconds())
    #messages.append(summary_msg)
    #summary = summary_msg.content

    #assert(summary != None)

    # output the result, then return it
    #console.print(Panel(summary, title="ExecutorAgent Output"))

    # try to get a list of findings (disabled for now)
    llm_gpt4 = ChatOpenAI(model="gpt-4o", temperature=0)
    messages.append(HumanMessage(content="Go through the commands and their outputs again and provide a list of findings and potential leads. All given findings and leads should be new and not have already been included in the initial findings/leads list. Findings should be self-contained and contain all information for subsequent operations to work upon them."))
    tik = datetime.datetime.now()
    findings = llm_gpt4.with_structured_output(PostAnalysis).invoke(messages)
    tok = datetime.datetime.now()
    #logger.write_llm_call('executor_summary', prompt='',
    #                  result=summary_msg.content,
    #                  costs=summary_msg.response_metadata,
    #                  duration=(tok-tik).total_seconds())
    console.print(Pretty(findings))

    # leads = leads + findings.leads
    print(str(leads))

    console.log("Finished low-level executor run..")

    return ExecutedTask(task, findings, history)
