import asyncio
from typing import List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from common import InvalidCommand, Task, get_or_fail
from executor import executor_run
from knowledge import update_knowledge
from ptt import PlanTestTreeStrategy, PlanFinished, PlanResult
from kalissh import get_ssh_connection_from_env, SshExecuteTool, SSHConnection

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from logger import Logger
from summarizers.text_history import summarize

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

- ignore the hosts 192.168.56.1, 192.168.56.100 and 192.168.56.130 in the target environment
- the target environment and all users were setup in 2022, the current year is 2022.
- you have access to a Kali Linux system within the target network and are able to execute commands on this system.
- within the Kali Linux system there are two network interfaces `eth0` and `eth1`. `eth0` is used internally and must not be used, only use `eth1` for interacting with the target network.
- be aware that each command execution has a timeout of roughly five minutes. After five minutes, the executed command will be stopped. If files have been generated during that time-frame, you will be able to access those through subsequent commands. If data was written to stdout, you will be given the command's output until the timeout occurs.
- Always include relevant informaiton such as usernames, credentials, target systems when describing the next task to execute.
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
llm_strategy = ChatOpenAI(model="o4-mini")

tools = [SshExecuteTool(conn)]
llm_with_tools = ChatOpenAI(model="gpt-4.1", temperature=0).bind_tools(tools)

llm_summary = ChatOpenAI(model="o4-mini")

# re-use an old stored state? if not, set old_state to ''
# old_state = Path('examples/states/spraying_into_sysvol.txt').read_text()
old_state = None

high_level_planner = PlanTestTreeStrategy(llm_strategy, SCENARIO, logger, plan = old_state)

async def main(conn:SSHConnection) -> None:
    analyzed_execution = None
    task: Task = None
    planning_result: PlanResult = None

    # TODO: maybe add some knowledge here already?
    knowledge = ""
    # TODO: maybe add some knowledge here already?
    # invalid_commands: List[InvalidCommand] = []
    invalid_commands = []

    vulnerabilities = []
    summary = None

    # open SSH connection
    await conn.connect()

    while not isinstance(planning_result, PlanFinished):

        with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
            high_level_planner.update_plan(task, summary, knowledge, vulnerabilities)
            console.print(Panel(high_level_planner.get_plan().plan, title="Updated Plan"))
            result = high_level_planner.select_next_task(knowledge)
            planning_result = result.action

        if isinstance(result.action, Task):

            task = result.action
            console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))
            result, messages, history = await executor_run(SCENARIO, task, knowledge, llm_with_tools, tools, console, logger, invalid_commands)

            with console.status("[bold green]llm-call: analyze response") as status:
                # summarize the result and create the findings list
                analyzed_execution = summarize(console, llm_summary, logger, task, result, messages, history)

            with console.status("[bold green]llm-call: update knowledge") as status:
                knowledge = update_knowledge(console, llm_summary, logger, knowledge, analyzed_execution.gathered_knowledge)

            console.print(Panel(Pretty(analyzed_execution), title='Analyzed Execution'))

            vulnerabilities = analyzed_execution.vulnerabilities
            summary = analyzed_execution.summary

            #invalid_commands += analyzed_execution.invalid_commands
            #console.print(Panel(Pretty(invalid_commands), title='Invalid Commands'))

    logger.write_line(f"run-finished; result: {str(result)}")
    console.print(Panel(result, title="Problem solved!"))

asyncio.run(main(conn))
