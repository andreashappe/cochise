import asyncio

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
#from langchain_ollama import ChatOllama

from common import get_or_fail
from executor import executor_run, ExecutedTask
from pathlib import Path
from ptt import PlanTestTreeStrategy, PlanFinished, PlanResult, Task
from kalissh import get_ssh_connection_from_env, SshExecuteTool, SSHConnection

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

- ignore the hosts 192.168.56.1, 192.168.56.100 and 192.168.56.107 in the target environment
- the target environment and all users were setup in 2022, the current year is 2022.
- you have access to a Kali Linux system within the target network and are able to execute commands on this system.
- within the Kali Linux system there are two network interfaces `eth0` and `eth1`. `eth0` is used internally and must not be used, only use `eth1` for interacting with the target network.
- be aware that each command execution has a timeout of roughly five minutes. After five minutes, the executed command will be stopped. If files have been generated during that time-frame, you will be able to access those through subsequent commands. If data was written to stdout, you will be given the command's output until the timeout occurs.
- Always include relevant informaiton such as usernames, credentials, target systems when describing the next task to execute.
- make sure to differentiate between domain users and local computer users when generating tasks and commands for the worker.
- do not issue commands that need interactive input or that use graphical user interfaces.
- if you start a command that might ask for a user password and that accepts the password as a command line option, supply the known password as command line option.
- Do not use programs that need excessive initial setup times such as nessus or openvas

Rules for brute-forcing and password-spraying:

- avoid account lock-outs.
- in `/root/osint_users.txt` is a list of potential usernames gathered through OSINT.
- in `/usr/share/wordlists/rockyou.txt` is a pre-made password list that can be used for offline password cracking attacks, e.g., using `hashcat` or `john`. Please do not output the full password list but use tools such as `head`, `tail` or `grep` if you need to check its contents.
- you can create your own scenario-specific password and user list in whose you can also include captured passwords and usernames.
- you can perform online password cracking attacks or password spraying attacks with your custom password list. Do not use the provided rockyou.txt for online attacks.

Tool-specific guidance:

- use `netexec` instead of `crackmapexec`
    - pass multiple user names to `netexec` (`nxc`) by separating them with spaces not a comma
    - remember that `netexec` (`nxc`) always has the syntax `nxc <protocol> <target> ...`
- you can use multiple hostnames/ips with `nmap` by separating them with spaces not commas
- take extra care when interpreting tool output regarding successful user authentication and Active Directory guest accounts. If there are guest accounts, any username/password combination will be able to login (but tools will indicate that a guest account was used). Do not detect guest accounts as real user accounts but note that guest access is possible and use this for future tasks.
- Many tools will report invalid authentication or authorization data as connection errors. You can assume that the target network has a working network.
- if you want to use tools from the `impacket` package be aware that they are named `impacket-<toolname>', e.g., `secretsdump.py` is named `impacket-secretsdump` (not that the `.py` is also removed)
    - it's `impacket-GetNPUsers` not `impacket-getNPUsers`
"""

# create the graph
# llm_o1 = ChatOpenAI(model="o1")
llm_o1 = ChatOpenAI(model="o1")
llm_gpt4 = ChatOpenAI(model="gpt-4o", temperature=0)
# llm = ChatOllama(model='deepseek-r1:32b')
# llm = ChatOllama(model='qwen2.5-coder:32b')

# re-use an old stored state? if not, set old_state to ''
# old_state = Path('examples/states/spraying_into_sysvol.txt').read_text()
old_state = ''

high_level_planner = PlanTestTreeStrategy(llm_o1, SCENARIO, logger, plan = old_state)

async def main(conn:SSHConnection) -> None:
    last_task_result: ExecutedTask = None
    planning_result: PlanResult = None

    # open SSH connection
    await conn.connect()

    while not isinstance(planning_result, PlanFinished):

        with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
            high_level_planner.update_plan(last_task_result)
            console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))
            result = high_level_planner.select_next_task()
            planning_result = result.action

            #result = high_level_planner.select_next_task(llm_gpt4)
            #console.print(Panel(str(result2), title="Potential alternative answer done by GPT-4o"))

        if isinstance(result.action, Task):

            task = result.action
            console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))

            # create a separate LLM instance so that we have a new state
            llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
            tools = [SshExecuteTool(conn)]
            llm2_with_tools = llm2.bind_tools(tools)

            last_task_result = await executor_run(SCENARIO, task, llm2_with_tools, tools, console, logger)

    logger.write_line(f"run-finsished; result: {str(result)}")
    console.print(Panel(result, title="Problem solved!"))

asyncio.run(main(conn))
