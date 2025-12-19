import datetime
import pathlib
from typing import List

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from common import AnalyzedExecution
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
TEMPLATE_KNOWLEDGE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'update_knowledge.md.jinja2'), template_format='jinja2')

PROMPT = """You are a professional penetration tester and are analying the log trace
of recently executed commands. The commands were executed on a Kali linux
virtual machine and target an Active Directory network as target environment.

Analyze the log trace for knowledge about the target environment (the Active
Directory network). Do not include information about the Kali Linux virtual
machine or the tools used. Focus on the target environment and the
information gathered from the executed commands.

The goal is to extract concise and 
actionable knowledge from the provided traces and enrich the provided
summary with additional information gathered from the traces while keeping
it concise.
"""

def message_based_summarize(console, logger, llm, messages):

    # try to get a list of findings (disabled for now)
    messages.append(HumanMessage(content=PROMPT))
    tik = datetime.datetime.now()
    result = llm.with_structured_output(AnalyzedExecution, include_raw=True).invoke(messages)
    analyzed = result['parsed']
    tok = datetime.datetime.now()

    print(str(result['raw'].response_metadata))
    logger.write_llm_call('summarizer', prompt='',
                      result=analyzed,
                      costs=result['raw'].response_metadata,
                      duration=(tok-tik).total_seconds())
    console.print(Panel(Pretty(analyzed), title="message based findings"))

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

class InitialAnalyzer:
    def __init__(self, llm, console:Console, logger):
        self.llm = llm
        self.console = console
        self.logger = logger

    def analyze_executor(self, summary:str, messages:List[str]):

        # output the result, then return it
        if summary != None and len(summary) > 0:
            self.console.print(Panel(summary, title="ExecutorAgent Output"))
        else:
            self.console.print(Panel('no summary provided', title="ExecutorAgent Output"))

        tmp = message_based_summarize(self.console, self.logger, self.llm, messages)

        if summary == None or len(summary) == 0:
           summary = tmp.summary 

        return summary, '\n'.join(tmp.gathered_knowledge)
