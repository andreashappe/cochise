import datetime

from langchain_core.messages import HumanMessage

from ptt import ExecutedTask, PostAnalysis
from rich.pretty import Pretty
from rich.panel import Panel

PROMPT = """
Go through the commands and their outputs and analyze
them for potential problems, additional attack vectors, and
concrete facts/information contained within the logs.

Be concise but include sufficient information that another
worker can continue analysis.
"""

def summarize(console, llm, task, summary, messages, history):

    # output the result, then return it
    if summary != None:
        console.print(Panel(summary, title="ExecutorAgent Output"))
    else:
        console.print(Panel('no summary provided', title="ExecutorAgent Output"))

    # try to get a list of findings (disabled for now)
    messages.append(HumanMessage(content=PROMPT))
    tik = datetime.datetime.now()
    findings = llm.with_structured_output(PostAnalysis).invoke(messages)
    tok = datetime.datetime.now()

    if summary != None:
        findings.summary = summary

    #logger.write_llm_call('executor_summary', prompt='',
    #                  result=summary_msg.content,
    #                  costs=summary_msg.response_metadata,
    #                  duration=(tok-tik).total_seconds())
    console.print(Pretty(findings))
    console.log("Finished low-level executor run..")

    return ExecutedTask(task, findings, history)