import datetime
import pathlib

from dataclasses import dataclass
from functools import reduce
from logger import Logger
from typing import Union, Dict, List
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_UPDATE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_update.md.jinja2'), template_format='jinja2')
TEMPLATE_NEXT   = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_next.md.jinja2'), template_format='jinja2')

class UpdatedPlan(BaseModel):
    """This is the updated plan that contains all proposed changes."""

    plan: str = Field(
        description="the newly updated plan"
    )

class Task(BaseModel):
    """Next Task to execute and analyze"""

    next_step: str = Field(
        description = "The next task to perform."
    )

    next_step_context: str = Field(
        description = "Context for worker that executes the next step"
    )

class PlanFinished(BaseModel):
    """Response to user."""
    response: str

class PlanResult(BaseModel):
    """Action to perform."""

    action: Union[PlanFinished, Task] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

@dataclass
class ExecutedTask:
    task: Task
    summary: str
    cmd_history: List[Dict[str, str]]
    
class PlanTestTreeStrategy:

    plan: str
    logger: Logger
    scenario: str

    def __init__(self, llm, scenario, logger, plan=''):
        self.llm = llm
        self.scenario = scenario
        self.logger = logger
        self.plan = plan

    def update_plan(self, last_task: ExecutedTask) -> None:

        if last_task != None:
            history_size = reduce(lambda value, x: value + len(x['cmd']) + len(x['result']), last_task.cmd_history, 0)
            if history_size >= 100000:
                print(f"!!! warning: history size {history_size} >= 100.000, removing it to cut down costs")
                last_task.cmd_history = []

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
            'last_task': last_task
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

        self.plan = result['parsed'].plan

    def select_next_task(self, llm=None) -> PlanResult:

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
        }

        if llm == None:
            llm = self.llm

        select = TEMPLATE_NEXT | llm.with_structured_output(PlanResult, include_raw=True)
        tik = datetime.datetime.now()
        result = select.invoke(input)
        tok = datetime.datetime.now()

        # output tokens
        print(str(result['raw'].response_metadata))

        if isinstance(result['parsed'].action, PlanFinished):
            self.logger.write_llm_call('strategy_finished', 
                                       TEMPLATE_NEXT.invoke(input).text,
                                       result['parsed'].action.response,
                                       result['raw'].response_metadata,
                                       (tok-tik).total_seconds())
        else:
            self.logger.write_llm_call('strategy_next_task', 
                                       TEMPLATE_NEXT.invoke(input).text,
                                       {
                                            'next_step': result['parsed'].action.next_step,
                                            'next_step_context': result['parsed'].action.next_step_context
                                       },
                                       result['raw'].response_metadata,
                                       (tok-tik).total_seconds())
        return result['parsed']
    
    def get_plan(self) -> str:
        return self.plan
