# split out the low-level executor

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages.tool import ToolMessage
from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

from rich.panel import Panel


# the task executor
class ExecutorState(TypedDict):
    messages: Annotated[list, add_messages]

def executor_run(SCENARIO, task, llm2_with_tools, tools, console, logger):

    logger.info("Agent Started!", op="agent_start", task=task)

    prompt = PromptTemplate.from_template(SCENARIO + """
    To achieve this, focus upon {task}

    Do not repeat already tried escalation attacks. You should focus upon
    enumeration and privilege escalation.
                                          
    If you were able to achieve the
    task, describe the used method as final message. Stop after 5 executions.
    If not successful until then, give a summary of gathered facts.
    """).format(task=task)

    # create our command executor/agent graph
    graph_builder = StateGraph(ExecutorState)

    # this is still named chatbot as we copied it from the langgraph
    # example code. This should rather be named 'hackerbot' or something
    def chatbot(state: ExecutorState):
        if len(state["messages"]) > 0:
            last_message = state["messages"][-1]
            if isinstance(last_message, ToolMessage):
                logger.info("Result from Tool", op="tool_result", result=last_message.content)
                console.print(Panel(last_message.content, title="Tool Result"), markup=False)

        next_step = llm2_with_tools.invoke(state["messages"])

        # if toolcall: what was the toolcall?
        result = "\n".join(list(map(lambda x: f"{x['name']}: '{x['args']['command']}'", next_step.tool_calls)))
        console.print(Panel(result, title="Tool Call(s)"))
        logger.info("Calling Tools", op="tool_call", tools=result)
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
        print(str(event))
        agent_response = event

    final_message = agent_response["messages"][-1].content

    console.print(Panel(final_message, title="ExecutorAgent Output"))
    logger.info("Agent Result!", op="agent_result", result=final_message)

    # add the last message (which should include a summary) to the global
    # past_steps collection
    # TODO: replace this with a better memory mechanism
    return {
        "past_steps": [(task, final_message)],
    }
