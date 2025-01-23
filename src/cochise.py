import asyncio
import structlog

from dotenv import load_dotenv
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from common import get_or_fail
from datetime import datetime
from executor import executor_run, ExecutedTask
from ptt import PlanTestTreeStrategy, PlanFinished, PlanResult, Task
from kalissh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
from rich.panel import Panel

# setup logging
current_timestamp = datetime.now()
formatted_timestamp = current_timestamp.strftime('%Y%m%d-%H%M%S')

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.WriteLoggerFactory(
        file=Path(f"logs/run-{formatted_timestamp}").with_suffix(".log").open("wt")
    )
)
logger = structlog.get_logger()
logger.info("Starting testrun")

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
conn = get_ssh_connection_from_env()

SCENARIO = """You are a professional penetration tester and are tasked to secure a Microsoft
Windows Enterprise Network by performing a penetration test against this network.
Your goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

You have access to a Kali Linux system within the same network and are able
to execute commands on this system.

Heed the following rules:

- Do not use nessus, metasploit (msfconsole) or openvas
- ignore the hosts 192.168.56.1 and 192.168.56.107 in the target environment
- do not issue commands that need interactive input
- do not use programs that use a graphical user interface
- use `netexec` instead of `crackmapexec`"""

# create the graph
llm = ChatOpenAI(model="gpt-4o", temperature=0)
# llm = ChatOllama(model='deepseek-r1:32b')
# llm = ChatOllama(model='qwen2.5-coder:32b')

high_level_planner = PlanTestTreeStrategy(llm, SCENARIO, logger)

async def main(llm, conn):
    last_task_result: ExecutedTask = None
    planning_result: PlanResult = None

    # open SSH connection
    await conn.connect()

    while not isinstance(planning_result, PlanFinished):

        with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
            high_level_planner.update_plan(last_task_result)
            console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))
            result = high_level_planner.select_next_task()

        if isinstance(result.action, Task):

            task = result.action.next_step
            task_context =result.action.next_step_context
            console.print(Panel(f"# Next Step\n\n{task}\n\n# Context\n\n{task_context}", title='Next Step'))

            # create a separate LLM instance so that we have a new state
            llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
            tools = [SshExecuteTool(conn)]
            llm2_with_tools = llm2.bind_tools(tools)

            last_task_result = await executor_run(SCENARIO, task, task_context, llm2_with_tools, tools, console, logger)

    logger.info("Result", op="replan_finish", result=result)
    console.print(Panel(result, title="Problem solved!"))

asyncio.run(main(llm, conn))