import datetime
import pathlib

from common import AnalyzedExecution, Task
from logger import Logger
from typing import Union, List
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_UPDATE = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_update.md.jinja2'), template_format='jinja2')
TEMPLATE_NEXT   = PromptTemplate.from_file(str(TEMPLATE_DIR / 'ptt_next.md.jinja2'), template_format='jinja2')

class UpdatedPlan(BaseModel):
    """This is the updated plan that contains all proposed changes."""

    plan: str = Field(
        description="the newly updated hierchical plan."
    )

    successful_attacks: List[str] = Field(
        description="List all concrete attacks that were successful in the target environment."
    )

    findings: List[str] = Field(
        description="This is a list of potential findings gathered for the target environment."
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

class PlanTestTreeStrategy:

    plan: UpdatedPlan = None
    logger: Logger
    scenario: str

    def __init__(self, llm, scenario, logger, plan=None):
        self.llm = llm
        self.scenario = scenario
        self.logger = logger
        self.plan = plan

    def update_plan(self, last_task: Task, analysis: AnalyzedExecution) -> None:

        if self.plan == None:
            target_plan = ''
        else:
            target_plan = self.plan.plan

        input = {
            'user_input': self.scenario,
            'plan': target_plan,
            'last_task': last_task,
            'analysis': analysis
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
        self.plan = result['parsed']

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
