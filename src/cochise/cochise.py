import asyncio
import pathlib

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from cochise.agent_analyzer import AgentAnalyzer
from cochise.common import Task, get_or_fail
from cochise.executor import executor_run
from cochise.logger import Logger
from cochise.kalissh import get_ssh_connection_from_env, SSHConnection
from cochise.ptt import PlanTestTreeStrategy

# setup logggin console for now
console = Console()

# setup configuration from environment variables
load_dotenv()
conn = get_ssh_connection_from_env()

logger = Logger()
logger.write_line("starting testrun")

SCENARIO = (pathlib.Path(__file__).parent / "templates" / "scenario.md").read_text()

tools = [conn.execute_command]

# TODO: we could use a cached (auto-generated) plan here instead of
# creating a new one every run

model = get_or_fail("LITELLM_MODEL")
api_key = get_or_fail("LITELLM_API_KEY")

high_level_planner = PlanTestTreeStrategy(model, api_key, SCENARIO, logger, plan = None)

async def main(conn:SSHConnection) -> None:
    task: Task = None

    analyzer = AgentAnalyzer(model, api_key, console, logger)
    knowledge = ""

    # open SSH connection
    await conn.connect()

    # create an initial plan and select the first task 
    with console.status("[bold green]llm-call: creating initial plan and selecting next task") as status:
        high_level_planner.create_initial_plan()
        console.print(Panel(high_level_planner.get_plan(), title="Initial Plan"))
        result = high_level_planner.select_next_task(knowledge)

    # work and update the plan until we have no tasks left, i.e., the problem is solved
    while isinstance(result.action, Task):

        task = result.action
        console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title=f'Next Step ({task.mitre_attack_tactic}/{task.mitre_attack_technique})'))
        knowledge = analyzer.get_knowledge()
        result, messages = await executor_run(SCENARIO, task, knowledge, model, api_key, tools, console, logger)

        with console.status("[bold green]llm-call: analyze response and update plan") as status:
            analyzer.analyze_executor(task, result, messages, high_level_planner)
            try:
                console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))
            except Exception as e:
                console.print(f"Error while printing updated plan: {e}")
                console.print(high_level_planner.get_plan())

        with console.status("[bold green]llm-call: selecting next task") as status:
            result = high_level_planner.select_next_task(knowledge)

    logger.write_line(f"run-finished; result: {str(result)}")
    console.print(Panel(Pretty(result.action), title="Hacking Run finished!"))

asyncio.run(main(conn))
