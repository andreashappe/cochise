from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage

from rich.panel import Panel

PROMPT = """
To achieve the scenario, focus upon the following task:
                                      
`{task}`
                                      
You are given the following context that might help you achieving that task:

```                                
{context}
```

If you were able to achieve the task, describe the used method as final message.
"""

def executor_run(SCENARIO, task, context, llm2_with_tools, tools, console, logger):

    # create a string -> tool mapping
    mapping = {}
    for tool in tools:
        mapping[tool.__class__.__name__] = tool

    # tool_call history
    history = []

    # how many rounds will we do?
    MAX_ROUNDS: int = 5

    # the initial prompt
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=SCENARIO),
            HumanMessagePromptTemplate.from_template(PROMPT)
        ]
    )

    # our message history
    messages = chat_template.format_messages(task=task, context=context)

    # try to solve our sub-task
    round = 1
    summary = "Was not able to achieve task"
    while round <= MAX_ROUNDS:
        ai_msg = llm2_with_tools.invoke(messages)
        messages.append(ai_msg)

        if hasattr(ai_msg, "tool_calls") and len(ai_msg.tool_calls) > 0:

            # output a summary before we do the acutal tool calls
            result = "\n".join(list(map(lambda x: f"{x['name']}: {x['args']['command']}", ai_msg.tool_calls)))
            console.print(Panel(result, title="Tool Call(s)"))
            logger.info("Calling Tools", op="tool_call", tools=result)

            # perform all tool calls
            for tool_call in ai_msg.tool_calls:
                selected_tool = mapping[tool_call["name"]]
                cmd = tool_call["args"]["command"]
                tool_msg = selected_tool.invoke(tool_call)

                console.print(Panel(tool_msg.content, title=f"Tool Result for {cmd}"), markup=False)
                history.append({
                    'tool': tool_call['name'],
                    'cmd': cmd,
                    'finished': True,
                    'result': tool_msg.content
                })
                messages.append(tool_msg)
        else:
            # the AI message has not tool_call -> this was some sort of result then
            # TODO: maybe use structured output so that we do not have this ugly if
            # TODO: ai_msg also has token counts, capture those too
            summary = ai_msg.content
            break
        round = round + 1

    # output the result, then return it
    console.print(Panel(summary, title="ExecutorAgent Output"))
    logger.info("Agent Result!", op="agent_result", result=summary, task=task, executed_commands=history)

    return {
        'task': task,
        'summary': summary,
        'executed_commands': history
    }