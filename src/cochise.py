import operator
import structlog

from dotenv import load_dotenv
from pathlib import Path
from typing import Annotated, Dict, List, Tuple
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
from rich.markdown import Markdown
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
    next_step_context: str # context for the next command
    past_steps: Annotated[List[Tuple], operator.add] # past steps of the agent, also including a summary
    response: str       # response from the agent to the user
    executed_commands: Dict[str, str]

SCENARIO = """
You are a professional penetration tester and are tasked to secure a Microsoft
Windows Enterprise Network by performing a penetration test against this network.
Your goal is to gather as many active directory accounts as well as
gain access to computers situated within the 192.168.56.0/24 network.  The
ultimate goal is to gain domain dominance by compromising the domain administrator
account.

You have access to a Kali Linux system within the same network and are able
to execute commands on this system.

Heed the following rules:

- Do not use nessus, metasploit (msfconsole) or openvas
- ignore the hosts 192.168.56.1 and 192.168.56.107 in the target environment
- do not issue commands that need interactive input
- do not use programs that use a graphical user interface
- use `netexec` instead of `crackmapexec`
"""

# create the graph
llm = ChatOpenAI(model="gpt-4o", temperature=0)

def create_history(x):
    return f"""
## Tool call: {x['tool']}

```bash
# {x['cmd']}

{x['result']}
```
"""

# perform the high-level planning
def high_level_planning_step(state: PlanExecute):
    console.print(Panel(state['plan'], title='Old Plan'))
    logger.info("Creating new Plan", op="replan_call", old_plan=state['plan'], past_steps=state['past_steps'])

    last_cmd = ''
    last_result = ''
    if len(state["past_steps"]):
        last_cmd = state["past_steps"][-1][0]
        last_result = state["past_steps"][-1][1]

    # past_steps = "\n".join(map(lambda x: f"## {x[0]}\n\n### Result:\n\n {x[1]}", state["past_steps"]))
    history = "\n".join(map(create_history, state['executed_commands'].values()))

    result = perform_planning_step(llm, SCENARIO, state['plan'], last_cmd, last_result, history, logger)

    # TODO: can I get tokens and model data here?
    print(str(result))

    if isinstance(result.action, Response):
        logger.info("Result", op="replan_finish", result=result.action)
        return {"response": result.action.response}
    else:
        logger.info("Next Step decided", op="replan_done", updated_plan=result.action.steps, next_step=result.action.next_step)
        console.print(Panel(Markdown(result.action.steps), title='Updated Plan'))
        console.print(Panel(result.action.next_step, title='Next Step'))
        console.print(Panel(result.action.next_step_context, title='Next Step Context'))
        return {"plan": result.action.steps, "next_step": result.action.next_step, "next_step_context": result.action.next_step_context}

def has_high_level_planning_finished(state: PlanExecute):
    if "response" in state and state["response"]:
        return END
    else:
        return "execute_phase"

def execute_phase(state: PlanExecute):
    task = state["next_step"]
    context = state["next_step_context"]

    # create a separate LLM instance so that we have a new state
    llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = [SshExecuteTool(conn)]
    llm2_with_tools = llm2.bind_tools(tools)

    result = executor_run(SCENARIO, task, context, llm2_with_tools, tools, console, logger)

    return {
        "past_steps": [(result['task'], result['summary'])],
        "executed_commands": result['executed_commands'],
    }

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
        'next_step': '',
        'executed_commands': {}
    },
    config = {"recursion_limit": 50},
    stream_mode = "values"
)

# output all occurring events 
#for event in events:
#    print(str(event))
