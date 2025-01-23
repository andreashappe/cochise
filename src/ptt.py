import pathlib

from dataclasses import dataclass
from typing import Union, Dict, List
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate
from structlog import BoundLogger

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
    task: str
    summary: str
    cmd_history: List[Dict[str, str]]
    
class PlanTestTreeStrategy:

    plan: str
    logger: BoundLogger
    scenario: str

    def __init__(self, llm, scenario, logger, plan=''):
        self.llm = llm
        self.scenario = scenario
        self.logger = logger
        self.plan = plan

    def update_plan(self, last_task: ExecutedTask) -> None:

        self.logger.info("Updating existing Plan", op="replan_call", old_plan=self.plan)

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
            'last_task': last_task
        }

        print(TEMPLATE_UPDATE.invoke(input).text)
        replanner = TEMPLATE_UPDATE | self.llm.with_structured_output(UpdatedPlan, include_raw=True)
        result = replanner.invoke(input)

        # output tokens
        metadata=result['raw'].response_metadata
        print(str(metadata))

        self.plan = result['parsed'].plan

    def select_next_task(self) -> PlanResult:

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
        }

        print(TEMPLATE_NEXT.invoke(input).text)
        select = TEMPLATE_NEXT | self.llm.with_structured_output(PlanResult, include_raw=True)
        result = select.invoke(input)

        # output tokens
        metadata=result['raw'].response_metadata
        print(str(metadata))
        return result['parsed']
    
    def get_plan(self) -> str:
        return self.plan