import operator

from dotenv import load_dotenv
from typing import Annotated, List, Tuple, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from common import get_or_fail
from executor import executor_run
from ssh import get_ssh_connection_from_env, SshExecuteTool

from rich.console import Console
from rich.panel import Panel

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

PLANNER_PROMPT = """
You are given an objective by the user. You are required to strategize and create
a tree-structured task plan that will allow to successfully solve the objective.
Another worker will follow your task plan to complete the objective, and will
report after each finished task back to you. You should use this feedback to update
the task plan.

When creating the task plan you must follow the following requirements:

1. You need to maintain a task plan, which contains all potential tasks that should
be investigated to solve the objective. The tasks should be in a tree structure because
one task can be considered as a sub-task to another. 

You can display the tasks in a layer structure, such as 1, 1.1, 1.1.1, etc. Initially,
you should only generate the root tasks based on the initial information. This plan
should involve individual tasks, that if executed correctly will yield the
correct answer. Do not add any superfluous steps but make sure that each step has
all the information needed - do not skip steps.

2. Each time you receive results from the worker you should 
2.1 Analyze the message and see identify useful key information
2.2 Decide to add a new task or update a task information according to the findings.
Only add steps to the plan that still NEED to be done.
2.3 Decide to delete a task if necessary. Do this if the task is not relevant for
reaching the objective anymore.
2.4 From all the tasks, identify those that can be performed next. Analyze those
tasks and decide which one should be performed next based on their likelihood to a
successful exploit. Name this task as 'next_step'.
    
Your objective was this:
{user_input}

Your original task-plan was this:
{plan}

You have currently done the follow tasks:
{past_steps}

If no more steps are needed to solve the objective, then respond with that. Otherwise,
return a new task-plan and the next step to execute. If you were not able to complete
the task, stop after 15 planning steps and give a summary to the user.

In addition select the next task (as next_step) that should be executed by the tester.
Include all needed information that the tester will need to execute the task within
next_step.
"""

# create the graph
llm = ChatOpenAI(model="gpt-4o", temperature=0)

### Planner component: response data-type (main type: Act)
class Plan(BaseModel):
    """Plan to follow in future"""

    steps: str = Field(
        description="the hierarchical task plan"
    )

    next_step: str = Field(
        description = "The next task to perform."
    )

class Response(BaseModel):
    """Response to user."""
    response: str

class Act(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

# perform the high-level planning
def high_level_planning_step(state: PlanExecute):
    replanner = ChatPromptTemplate.from_template(PLANNER_PROMPT) | llm.with_structured_output(Act)
    planner_input = f"""
Old Plan: {state['plan']}
Past Steps: {state['past_steps']}
    """
    console.print(Panel(planner_input, title='Planner Input'))
    result = replanner.invoke(state)

    if isinstance(result.action, Response):
        return {"response": result.action.response}
    else:
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

    return executor_run(SCENARIO, task, llm2_with_tools, tools, console)

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
events = app.stream(
    input = {
        "user_input": PromptTemplate.from_template(SCENARIO),
        "plan": '',
        'next_step': ''
    },
    config = {"recursion_limit": 50},
    stream_mode = "values"
)

# output all occurring events 
for event in events:
    print(str(event))
