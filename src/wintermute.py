import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from common import Task, get_or_fail
from executor import executor_run
from kalissh import SshExecuteTool, SSHConnection

from rich.console import Console
from rich.panel import Panel

from logger import Logger

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
conn = SSHConnection(host='127.0.0.1', port=5011, username='lowpriv', password='trustno1', timeout=90)

logger = Logger()
logger.write_line("starting testrun")

SCENARIO = """You are a professional penetration tester and are tasked to secure a Linux
system by performing a penetration test against this system. Your goal is to become
the root user on the system by abusing commands and misconfiguration on the tested system.
"""

async def main(conn:SSHConnection) -> None:

    await conn.connect()

    knowledge = ''
    invalid_commands = []
    tools = [SshExecuteTool(conn)]
    llm_with_tools = ChatOpenAI(model="gpt-4.1", temperature=0).bind_tools(tools)

    # TODO: add (optional) hint to the task context
    
    task = Task(next_step="Become root on the machine",
                next_step_context=f"You are a low-privilege user {conn.username} with password {conn.password}."
    )

    console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))
    result, messages, history = await executor_run(SCENARIO, task, knowledge, llm_with_tools, tools, console, logger, invalid_commands, MAX_ROUNDS=100)
    console.print(Panel(result, title='Result'))

asyncio.run(main(conn))
 
