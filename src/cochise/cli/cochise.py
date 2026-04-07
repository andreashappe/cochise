import asyncio
import litellm
import os
import pathlib

from dotenv import load_dotenv
from rich.console import Console

from cochise.common import get_or_fail
from cochise.executor import ExecutorFactory
from cochise.planner import Planner
from cochise.logger import Logger
from cochise.ssh_connection import get_ssh_connection_from_env

SCENARIO = (pathlib.Path(__file__).parent.parent / "templates" / "scenario.md").read_text()

async def async_main() -> None:

    # setup configuration from environment variables
    load_dotenv()
    conn = get_ssh_connection_from_env()

    # disable warnings about unknown models
    litellm.suppress_debug_info = True

    # setup logging and console output
    console = Console()
    logger = Logger(console)
    logger.log_data("starting test-run")

    # get model data and document configuration in the logs
    model = get_or_fail("LITELLM_MODEL")
    api_key = get_or_fail("LITELLM_API_KEY")

    # when should the high-level context be compressed/compacted. The executor's
    # context will be reset with each new executor (the planner's wont).
    planner_max_context_size = int(os.getenv("PLANNER_MAX_CONTEXT_SIZE", "250000"))
    planner_max_interactions = int(os.getenv("PLANNER_MAX_INTERACTIONS", "0"))

    # should we stop the planner on the first reaction after this time has eclipsed?
    max_runtime = int(os.getenv("MAX_RUN_TIME", "0"))

    logger.log_data("configuration", {
        "model": model,
        "ssh-host": conn.host,
        "ssh-user": conn.username,
        "scenario": SCENARIO,
        "max_runtime": max_runtime,
        "planner_max_context_size": planner_max_context_size,
        "planner_max_interactions": planner_max_interactions,
    }, output=False)

    # open SSH connection
    await conn.connect()

    # setup components..
    tools = [conn.execute_command]
    executor_factory = ExecutorFactory(model, api_key, SCENARIO, tools, logger)
    planner = Planner(model, api_key, SCENARIO, executor_factory, logger, max_runtime, planner_max_context_size, planner_max_interactions)

    # ..and run cochise!
    await planner.engage()

asyncio.run(async_main())