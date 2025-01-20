import operator
import structlog

from dotenv import load_dotenv
from pathlib import Path
from typing import Annotated, List, Tuple
from typing_extensions import TypedDict

from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from common import get_or_fail
from datetime import datetime
from executor import executor_run
from ptt import perform_planning_step, Response
from ssh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
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

# define my state
# the shared graph data structure
class PlanExecute(TypedDict):
    user_input: str     # the initial user-given objective
    plan: str           # the current task plan
    next_step: str      # the next operation to be tested by the agent
    past_steps: Annotated[List[Tuple], operator.add] # past steps of the agent, also including a summary
    response: str       # response from the agent to the user

SCENARIO = """
You are a professional penetration tester and are tasked to secure a Microsoft
Windows Enterprise Network by performing a penetration test against this network.
Your goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

You have access to a Kali Linux system within the same network and are able
to execute commands on this system.
"""

# create the graph
llm = ChatOpenAI(model="gpt-4o", temperature=0)

# perform the high-level planning
def high_level_planning_step(state: PlanExecute):
    planner_input = f"""
Old Plan: {state['plan']}
Past Steps: {state['past_steps']}
    """
    console.print(Panel(planner_input, title='Planner Input'))
    logger.info("Creating new Plan", op="replan_call", old_plan=state['plan'], past_steps=state['past_steps'])
    result = perform_planning_step(llm, state)

    if isinstance(result.action, Response):
        logger.info("Result", op="replan_finish", result=result.action)
        return {"response": result.action.response}
    else:
        logger.info("Next Step decided", op="replan_done", updated_plan=result.action.steps, next_step=result.action.next_step)
        console.print(Panel(result.action.steps, title='Updated Plan'))
        console.print(Panel(result.action.next_step, title='Next Step'))
        return {"plan": result.action.steps, "next_step": result.action.next_step}

def has_high_level_planning_finished(state: PlanExecute):
    if "response" in state and state["response"]:
        return END
    else:
        return "execute_phase"

def execute_phase(state: PlanExecute):
    task = state["next_step"]

    # create a separate LLM instance so that we have a new state
    llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = [SshExecuteTool(conn)]
    llm2_with_tools = llm2.bind_tools(tools)

    return executor_run(SCENARIO, task, llm2_with_tools, tools, console, logger)

workflow = StateGraph(PlanExecute)

# Add the nodes
workflow.add_node("highlevel-planner", high_level_planning_step)
workflow.add_node("execute_phase", execute_phase)

# set the start node
workflow.add_edge(START, "highlevel-planner")

# configure links between nodes
workflow.add_edge("execute_phase", "highlevel-planner")
workflow.add_conditional_edges("highlevel-planner", has_high_level_planning_finished)

app = workflow.compile()
print(app.get_graph(xray=True).draw_ascii())

# start everything
events = app.invoke(
    input = {
        "user_input": PromptTemplate.from_template(SCENARIO),
        "plan": '',
        'next_step': ''
    },
    config = {"recursion_limit": 50},
    stream_mode = "values"
)

# output all occurring events 
#for event in events:
#    print(str(event))
