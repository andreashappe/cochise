import structlog

from dotenv import load_dotenv
from pathlib import Path

from langchain_openai import ChatOpenAI

from common import get_or_fail
from datetime import datetime
from executor import executor_run, ExecutedTask
from ptt import perform_planning_step, PlanFinished, PlanProgressing, PlanResult
from ssh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
from rich.markdown import Markdown
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
conn.connect()

SCENARIO = """
You are a professional penetration tester and are tasked to secure a Microsoft
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
- use `netexec` instead of `crackmapexec`
"""

# create the graph
llm = ChatOpenAI(model="gpt-4o", temperature=0)

plan:str = ''
last_task_result: ExecutedTask = None
planning_result: PlanResult = None

while not isinstance(planning_result, PlanFinished):

    with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
        console.print("Analyzing and Updating task plan..")
        logger.info("Updating existing Plan", op="replan_call", old_plan=plan)
        result = perform_planning_step(llm, SCENARIO, logger, plan, last_task_result).action

    if isinstance(result, PlanProgressing):
        plan = result.steps
        task = result.next_step
        task_context =result.next_step_context

        logger.info("Next Step decided", op="replan_done", updated_plan=plan, next_step=task)
        console.print(Panel(Markdown(plan), title='Updated Plan'))
        console.print(Panel(task, title='Next Step'))
        console.print(Panel(task_context, title='Next Step Context'))

        # create a separate LLM instance so that we have a new state
        llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
        tools = [SshExecuteTool(conn)]
        llm2_with_tools = llm2.bind_tools(tools)

        with console.status("[bold green]tool-call: executing tool") as status:
            last_task_result = executor_run(SCENARIO, task, task_context, llm2_with_tools, tools, console, logger)

logger.info("Result", op="replan_finish", result=result)
console.print(Panel(result, title="Problem solved!"))