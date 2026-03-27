import asyncio
import pathlib

from dotenv import load_dotenv
from rich.console import Console

from cochise.common import get_or_fail
from cochise.executor import ExecutorFactory
from cochise.planner import Planner
from cochise.logger import Logger
from cochise.ssh_connection import get_ssh_connection_from_env

SCENARIO = (pathlib.Path(__file__).parent.parent / "templates" / "scenario.md").read_text()

async def main() -> None:

    # setup logggin console for now
    console = Console()

    # setup configuration from environment variables
    load_dotenv()
    conn = get_ssh_connection_from_env()

    logger = Logger()
    logger.write_line("starting testrun")

    model = get_or_fail("LITELLM_MODEL")
    api_key = get_or_fail("LITELLM_API_KEY")

    # open SSH connection
    await conn.connect()

    # setup cochise..
    tools = [conn.execute_command]
    executor_factory = ExecutorFactory(model, api_key, SCENARIO, tools, logger, console)
    planner = Planner(model, api_key, SCENARIO, executor_factory, logger, console)

    # ..and run it
    await planner.engage()

asyncio.run(main())