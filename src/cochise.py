import asyncio
import pathlib

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from common import Task, get_or_fail
from executor import executor_run
from ptt import PlanTestTreeStrategy
from kalissh import get_ssh_connection_from_env, SshExecuteTool, SSHConnection

from rich.console import Console
from rich.panel import Panel

from logger import Logger
from summarizers.initial_analyzer import InitialAnalyzer
from summarizers.agent_analzyer import AgentAnalyzer

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
conn = get_ssh_connection_from_env()

logger = Logger()
logger.write_line("starting testrun")

SCENARIO = (pathlib.Path(__file__).parent / "templates" / "scenario.md").read_text()

tools = [SshExecuteTool(conn)]

def setup_gemini_llms():
    model = 'gemini-3-flash-preview'

    llm_strategy = ChatGoogleGenerativeAI(
        model=model,
        max_tokens=None,
    )

    llm_with_tools = ChatGoogleGenerativeAI(
        model=model,
        max_tokens=None,
    ).bind_tools(tools)

    llm_summary = ChatGoogleGenerativeAI(
        model=model,
        max_tokens=None,
    )

    return llm_strategy, llm_with_tools, llm_summary

def setup_openai_llms():
    llm_strategy = ChatOpenAI(model="gpt-5-mini-2025-08-07")
    llm_with_tools = ChatOpenAI(model="gpt-5-mini-2025-08-07").bind_tools(tools)
    llm_summary = ChatOpenAI(model="gpt-5-mini-2025-08-07")

    return llm_strategy, llm_with_tools, llm_summary

llm_strategy, llm_with_tools, llm_summary = setup_gemini_llms()

# TODO: we could use a cached (auto-generated) plan here instead of
# creating a new one every run

high_level_planner = PlanTestTreeStrategy(llm_strategy, SCENARIO, logger, plan = None)

async def main(conn:SSHConnection) -> None:
    task: Task = None

    knowledge = ""
    summary = None

#    analyser = InitialAnalyzer(llm_summary, console, logger)
    analyser = AgentAnalyzer(llm_summary, console, logger)

    # open SSH connection
    await conn.connect()

    # create an initial plan and select the first task 
    with console.status("[bold green]llm-call: creating initial plan and selecting next task") as status:
        high_level_planner.create_initial_plan()
        console.print(Panel(high_level_planner.get_plan().plan, title="Initial Plan"))
        result = high_level_planner.select_next_task(knowledge)

    # work and update the plan until we have no tasks left, i.e., the problem is solved
    while isinstance(result.action, Task):

        task = result.action
        console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title=f'Next Step ({task.mitre_attack_tactic}/{task.mitre_attack_technique})'))
        result, messages = await executor_run(SCENARIO, task, knowledge, llm_with_tools, tools, console, logger)

        with console.status("[bold green]llm-call: analyze response and update plan") as status:
            analyser.analyze_executor(task, result, messages, high_level_planner)
            console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))

        with console.status("[bold green]llm-call: selecting next task") as status:
            result = high_level_planner.select_next_task(knowledge)

    logger.write_line(f"run-finished; result: {str(result)}")
    console.print(Panel(result, title="Hacking Run finished!"))

asyncio.run(main(conn))
