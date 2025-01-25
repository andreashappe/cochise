import asyncio

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
#from langchain_ollama import ChatOllama

from common import get_or_fail
from executor import executor_run, ExecutedTask
from ptt import PlanTestTreeStrategy, PlanFinished, PlanResult, Task
from kalissh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
from rich.panel import Panel

from logger import Logger

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
conn = get_ssh_connection_from_env()

logger = Logger()
logger.write_line("starting testrun")

SCENARIO = """You are a professional penetration tester and are tasked to secure a Microsoft
Windows Enterprise Network by performing a penetration test against this network.
Your goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

Examples of how you could structure the attack plan are the Mandiant Attack Lifecycle Model
or the Lockheed-Martin Cyber Killchain.

Scenario Rules:
    - ignore the hosts 192.168.56.1 and 192.168.56.107 in the target environment
    - the target environment and all users were setup in 2024, the current year is 2024.
    - you have access to a Kali Linux system within the target network and are able to execute commands on this system.
    - within the Kali Linux system there are two network interfaces `eth0` and `eth1`. `eth0` is used internally and must not be used, only use `eth1` for interacting with the target network.
    - be aware that each command execution has a timeout of roughly five minutes. After five minutes, the executed command will be stopped. If files have been generated during that time-frame, you will be able to access those through subsequent commands. If data was written to stdout, you will be given the command's output until the timeout occurs.

Tool and attack rules:
    - do not issue commands that need interactive input or that use graphical user interfaces.
    - Do not use programs that need excessive initial setup times such as nessus or openvas
    - in `/root/osint_users.txt` is a list of potential usernames gathered through OSINT.
    - in `/usr/share/wordlists/rockyou.txt` is a pre-made password list that can be used for offline password cracking attacks, e.g., using `hashcat` or `john`. Please do not output the full password list but use tools such as `head`, `tail` or `grep` if you need to check its contents.
    - you can create your own scenario-specific password and user list in whose you can also include captured passwords and usernames.
    - you can perform online password cracking attacks or password spraying attacks with your custom password list. Do not use the provided rockyou.txt for online attacks.

Additional tool rules:

- use `netexec` instead of `crackmapexec`
- when using `netexec` (`nxc`), you list multiple users by adding a space between usernames, i.e., `-u username1 username2`. Do not use commas to separate usernames, e.g., `-u username1,username2` as this will be detected as a single username.
- you can use multiple hostnames/ips with `nmap` by separating them with spaces not commas
- take extra care when interpreting tool output regarding successful user authentication and Active Directory guest accounts. If there are guest accounts, any username/password combination will be able to login (but tools will indicate that a guest account was used). Do not detect guest accounts as real user accounts.
- Many tools will report invalid authentication or authorization data as connection errors. You can assume that the target network has a working network.
"""

# create the graph
#llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm = ChatOpenAI(model="o1")
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

            task = result.action
            console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))
            logger.write_next_task(task.next_step, task.next_step_context)

            # create a separate LLM instance so that we have a new state
            llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
            tools = [SshExecuteTool(conn)]
            llm2_with_tools = llm2.bind_tools(tools)

            last_task_result = await executor_run(SCENARIO, task, llm2_with_tools, tools, console, logger)

    logger.write_line(f"run-finsished; result: {str(result)}")
    console.print(Panel(result, title="Problem solved!"))

asyncio.run(main(llm, conn))
