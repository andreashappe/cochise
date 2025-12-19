import datetime
import pathlib
from typing import List

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from common import Task, AnalyzedExecution
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
TEMPLATE_RESULT = PromptTemplate.from_file(str(TEMPLATE_DIR / 'summarizer.md.jinja2'), template_format='jinja2')
TEMPLATE_KNOWLEDGE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'update_knowledge.md.jinja2'), template_format='jinja2')

PROMPT = """
Go through the commands and their outputs and analyze
them for potential problems, additional attack vectors, and
concrete facts/information contained within the logs.

Be concise but include sufficient information that another
worker can continue analysis.
"""

def message_based_summarize(console, llm, task, summary, messages, history):

    # output the result, then return it
    if summary != None:
        console.print(Panel(summary, title="ExecutorAgent Output"))
    else:
        console.print(Panel('no summary provided', title="ExecutorAgent Output"))

    # try to get a list of findings (disabled for now)
    messages.append(HumanMessage(content=PROMPT))
    tik = datetime.datetime.now()
    result = llm.with_structured_output(AnalyzedExecution, include_raw=True).invoke(messages)
    analyzed = result['parsed']
    tok = datetime.datetime.now()

    #logger.write_llm_call('executor_summary', prompt='',
    #                  result=summary_msg.content,
    #                  costs=summary_msg.response_metadata,
    #                  duration=(tok-tik).total_seconds())
    console.print(Panel(Pretty(analyzed), title="message based findings"))
    console.log("Finished low-level executor run..")

    return analyzed

def update_knowledge(console:Console, llm, logger, knowledge:str, new_knowledge:List[str]) -> str:

    console.print(Panel(knowledge, title='Old Knowledge'))
    console.print(Panel(Pretty(new_knowledge), title='New Knowledge'))

    input = {
            'exisiting_knowledge': knowledge,
            'new_knowledge': new_knowledge
    }

    # try to get a list of findings (disabled for now)
    tik = datetime.datetime.now()
    summarizer = TEMPLATE_KNOWLEDGE| llm
    result = summarizer.invoke(input)
    aggregated = result.content
    tok = datetime.datetime.now()

    print(str(result.response_metadata))
    logger.write_llm_call('update_knowledge', prompt='',
                      result=aggregated,
                      costs=result.response_metadata,
                      duration=(tok-tik).total_seconds())

    console.print(Panel(aggregated, title='Aggregated Knowledge'))

    return aggregated

def summarize(console, llm, logger, task:Task, summary:str, messages, history) -> AnalyzedExecution:

    # output the result, then return it
    if summary != None:
        console.print(Panel(summary, title="ExecutorAgent Output"))
    else:
        console.print(Panel('no summary provided', title="ExecutorAgent Output"))

    input = {
            'task': task,
            'summary': summary,
            'history': history
    }

    # try to get a list of findings (disabled for now)
    tik = datetime.datetime.now()
    summarizer = TEMPLATE_RESULT| llm.with_structured_output(AnalyzedExecution, include_raw=True)
    result = summarizer.invoke(input)
    analyzed = result['parsed']
    tok = datetime.datetime.now()

    print(str(result['raw'].response_metadata))
    logger.write_llm_call('summarizer', prompt='',
                      result=analyzed,
                      costs=result['raw'].response_metadata,
                      duration=(tok-tik).total_seconds())
    console.print(Pretty(analyzed))
    console.log("Finished low-level executor run..")

    return analyzed

class InitialAnalyzer:
    def __init__(self, llm, console:Console, logger):
        self.llm = llm
        self.console = console
        self.logger = logger

    def analyze_executor(self, task:Task, result:str, messages:List[str], history:List[str]):

        # TODO: Test for differences
        message_based_summarize(self.console, self.llm, task, result, messages, history)

        tmp = summarize(self.console, self.llm, self.logger, task, result, messages, history)
        return tmp.summary, '\n'.join(tmp.gathered_knowledge)
