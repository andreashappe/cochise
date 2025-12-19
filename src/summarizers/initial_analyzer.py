import datetime
import pathlib
from typing import List

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage

from common import AnalyzedExecution, Task
from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel

from ptt import PlanTestTreeStrategy, UpdatedPlan

TEMPLATE_DIR = pathlib.Path(__file__).parent.parent / "templates"
TEMPLATE_UPDATE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_update.md.jinja2'), template_format='jinja2')
SCENARIO = (TEMPLATE_DIR / "scenario.md").read_text()

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

class InitialAnalyzer:
    def __init__(self, llm, console:Console, logger):
        self.llm = llm
        self.console = console
        self.logger = logger

    def analyze_executor(self, task: Task, result:str, messages:List[str], planner: PlanTestTreeStrategy) -> None:

        # output the result, then return it
        if result!= None and len(result) > 0:
            self.console.print(Panel(result, title="ExecutorAgent Output"))
        else:
            self.console.print(Panel('no result summary provided', title="ExecutorAgent Output"))

        # re-analyze the executed messages during the task execution
        tmp = message_based_summarize(self.console, self.logger, self.llm, messages)
        if result == None or len(result) == 0:
            summary = tmp.summary
        else:
            summary = result
        knowledge = '\n'.join(tmp.gathered_knowledge)

        # Use the new knowledge to update the PTT
        old_plan = planner.get_plan().plan

        input = {
            'user_input': SCENARIO,
            'plan': old_plan,
            'last_task': task,
            'summary': summary,
            'knowledge': knowledge,
        }

        replanner = TEMPLATE_UPDATE | self.llm.with_structured_output(UpdatedPlan, include_raw=True)
        tik = datetime.datetime.now()
        result = replanner.invoke(input)
        tok = datetime.datetime.now()

        # output tokens
        metadata=result['raw'].response_metadata
        print(str(metadata))

        self.logger.write_llm_call('strategy_update', 
                                   TEMPLATE_UPDATE.invoke(input).text,
                                   result['parsed'].plan,
                                   result['raw'].response_metadata,
                                   (tok-tik).total_seconds())
        planner.set_new_plan(result['parsed'])
