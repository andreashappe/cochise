import operator

from dotenv import load_dotenv
from typing import Annotated, List, Tuple, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages.tool import ToolMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from common import get_or_fail
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

# the task executor
class ExecutorState(TypedDict):
    messages: Annotated[list, add_messages]

def execute_phase(state: PlanExecute):
    task = state["next_step"]

    prompt = PromptTemplate.from_template(SCENARIO + """
    To achieve this, focus upon {task}

    Do not repeat already tried escalation attacks. You should focus upon
    enumeration and privilege escalation. If you were able to achieve the
    task, describe the used method as final message. Stop after 5 executions.
    If not successful until then, give a summary of gathered facts.
    """).format(task=task)

    # create a separate LLM instance so that we have a new state
    llm2 = ChatOpenAI(model="gpt-4o", temperature=0)
    tools = [SshExecuteTool(conn)]
    llm2_with_tools = llm2.bind_tools(tools)

    # create our command executor/agent graph
    graph_builder = StateGraph(ExecutorState)

    # this is still named chatbot as we copied it from the langgraph
    # example code. This should rather be named 'hackerbot' or something
    def chatbot(state: ExecutorState):
        if len(state["messages"]) > 0:
            last_message = state["messages"][-1]
            if isinstance(last_message, ToolMessage):
                console.print(Panel(last_message.content, title="Tool Result"), markup=False)

        next_step = llm2_with_tools.invoke(state["messages"])

        # if toolcall: what was the toolcall?
        result = "\n".join(list(map(lambda x: f"{x['name']}: '{x['args']['command']}'", next_step.tool_calls)))
        console.print(Panel(result, title="Tool Call(s)"))
        return {"messages": [next_step]}

    # Copied from the quickstart example, might be simplified
    def route_tools(state: ExecutorState):
        """
        Use in the conditional_edge to route to the ToolNode if the last message
        has tool calls. Otherwise, route to the end.
        """
        if isinstance(state, list):
            ai_message = state[-1]
        elif messages := state.get("messages", []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to tool_edge: {state}")
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END

    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools=tools))

    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", route_tools)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_edge("chatbot", END)
    graph = graph_builder.compile()

    # run subgraph till it finishes
    events = graph.stream(
        {"messages": [("user", prompt)]},
        stream_mode='values'
    )

    agent_response = None
    for event in events:
        # print(str(event))
        agent_response = event

    final_message = agent_response["messages"][-1].content
    console.print(Panel(final_message, title="ExecutorAgent Output"))

    # add the last message (which should include a summary) to the global
    # past_steps collection
    # TODO: replace this with a better memory mechanism
    return {
        "past_steps": [(task, final_message)],
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
