import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from common import Task, get_or_fail
from executor import executor_run
from knowledge import knowlege_to_attack_plan, update_knowledge
from ptt import PlanTestTreeStrategy
from kalissh import get_ssh_connection_from_env, SshExecuteTool, SSHConnection

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from rich.markdown import Markdown

from logger import Logger
from summarizer import summarize

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
The network could contain multiple domain controllers and multiple domains.
Your overall goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

Examples of how you could structure the attack plan are the Mandiant Attack Lifecycle Model
or the Lockheed-Martin Cyber Killchain.

Scenario Rules:

- do not repeat already tried attacks!
- ignore the hosts 192.168.56.1, 192.168.56.100 and 192.168.56.130 in the target environment
- the target environment and all users were setup in 2022, the current year is 2022.
- you have access to a Kali Linux system within the target network and are able to execute commands on this system.
- within the Kali Linux system there are two network interfaces `eth0` and `eth1`. `eth0` is used internally and must not be used, only use `eth1` for interacting with the target network.
- Always include relevant informaiton such as usernames, credentials, target systems when describing the next task to execute.
- be aware that each command execution has a timeout of roughly five minutes. After five minutes, you will get all captured output but the executed command will not be stopped automatically. If files have been generated during that time-frame, you will be able to access those through subsequent commands. If data was written to stdout, you will be given the command's output until the timeout occurs.
- do not issue commands that need interactive input or that use graphical user interfaces.
- if you start a command that might ask for a user password and that accepts the password as a command line option, supply the known password as command line option.
- Do not use programs that need excessive initial setup times such as nessus or openvas
- try to keep all generated files within your home directory.

Rules for brute-forcing and password-spraying:

- avoid account lock-outs but still use all supplied usernames for password spraying.
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

Don't overcomplicate things.
"""

# create the graph
llm_strategy = ChatOpenAI(model="o4-mini")

tools = [SshExecuteTool(conn)]
llm_executor = ChatOpenAI(model="gpt-4.1", temperature=0)
llm_summary = ChatOpenAI(model="gpt-4.1", temperature=0)
llm_knowledge = ChatOpenAI(model="o4-mini")

# re-use an old stored state? if not, set old_state to ''
# old_state = Path('examples/states/spraying_into_sysvol.txt').read_text()
old_state = None

high_level_planner = PlanTestTreeStrategy(llm_strategy, SCENARIO, logger, plan = old_state)

async def main(conn:SSHConnection) -> None:
    analyzed_execution = None
    task: Task = None
    done: bool = False

    knowledge = ""
    leads = ''
    findings = []
    invalid_commands = []
    task_history = []
    summary = None
    vulnerabilities = []

    # open SSH connection
    await conn.connect()

    while not done:

        with console.status("[bold green]llm-call: updating plan and selecting next task") as status:
            high_level_planner.update_plan(task, summary, knowledge, vulnerabilities, findings, leads)
            console.print(Panel(high_level_planner.get_plan().plan, title="Updated Plan"))
            result = high_level_planner.select_next_task(knowledge, leads, task_history)
        
        if isinstance(result.action, Task):
            task = result.action
            console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title='Next Step'))
            result, history = await executor_run(SCENARIO, task, knowledge, invalid_commands, llm_executor, tools, console, logger)

            with console.status("[bold green]llm-call: analyze response") as status:
                # summarize the result and create the findings list
                analyzed_execution = summarize(console, llm_summary, logger, SCENARIO, task, result, history)
                vulnerabilities = analyzed_execution.vulnerabilities
                console.print(Panel(Pretty(analyzed_execution), title='Analyzed Execution'))

            with console.status("[bold green]llm-call: update knowledge") as status:
                knowledge = update_knowledge(llm_knowledge, logger, knowledge, analyzed_execution.gathered_knowledge, vulnerabilities)
                findings = analyzed_execution.gathered_knowledge
                invalid_commands = analyzed_execution.invalid_commands
                console.print(Panel(Markdown(knowledge), title='Updated Knowledge'))

            task_history += task.next_step
            leads = analyzed_execution.potential_next_steps
            summary = analyzed_execution.summary

            knowlege_to_attack_plan(llm_knowledge, logger, SCENARIO, knowledge, high_level_planner.get_plan().plan)
        else:
            done = True

    console.print(Panel(Pretty(result), title='Plan Finished'))

asyncio.run(main(conn))
