import datetime
import pathlib

from common import Task
from logger import Logger
from typing import Union, List
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_UPDATE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_update.md.jinja2'), template_format='jinja2')
TEMPLATE_NEXT   = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_next.md.jinja2'), template_format='jinja2')

class PlanFinished(BaseModel):
    """Response to user."""
    response: str

class UpdatedPlan(BaseModel):
    """This is the updated plan that contains all proposed changes."""

    plan: str = Field(
        description="the newly updated hierchical plan."
    )

    #next_task: Union[PlanFinished, Task] = Field(
    #    description="The next task to perform. If you want to respond to user, use Response. "
    #    "If you need to further use tools to get the answer, use Plan."
    #)

class PlanResult(BaseModel):
    """Action to perform."""

    action: Union[PlanFinished, Task] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

class PlanTestTreeStrategy:

    plan: UpdatedPlan = None
    logger: Logger
    scenario: str

    def __init__(self, llm, scenario, logger, plan=None):
        self.llm = llm
        self.scenario = scenario
        self.logger = logger
        self.plan = plan

    def update_plan(self, last_task: Task, summary: str, knowledge: str, findings: str, leads: List[str], suggestions:str) -> Union[PlanFinished, Task]:

        if self.plan == None:
            target_plan = ''
        else:
            target_plan = self.plan.plan

        input = {
            'user_input': self.scenario,
            'plan': target_plan,
            'last_task': last_task,
            'summary': summary,
            'knowledge': knowledge,
            'findings': findings,
            'leads': leads,
            'suggestions': suggestions
        }

        replanner = TEMPLATE_UPDATE | self.llm.with_structured_output(UpdatedPlan, include_raw=True)
        tik = datetime.datetime.now()
        result = replanner.invoke(input)
        tok = datetime.datetime.now()

        self.logger.write_llm_call('strategy_update', 
                                   TEMPLATE_UPDATE.invoke(input).text,
                                   result['parsed'].plan,
                                   result['raw'].response_metadata,
                                   (tok-tik).total_seconds())
        self.plan = result['parsed']
        #return result['parsed'].next_task

    def select_next_task(self, knowledge, leads, task_history, llm=None) -> PlanResult:

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
            'knowledge': knowledge,
            'leads': leads,
            'task_history': task_history
        }

        if llm == None:
            llm = self.llm

        select = TEMPLATE_NEXT | llm.with_structured_output(PlanResult, include_raw=True)
        tik = datetime.datetime.now()
        result = select.invoke(input)
        tok = datetime.datetime.now()

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
