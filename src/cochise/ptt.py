import datetime
import pathlib
import litellm

from dataclasses import asdict, dataclass
from jinja2 import Template
from pydantic import BaseModel, Field
from typing import Any, Type

from cochise.common import Task
from cochise.logger import Logger

@dataclass
class UpdatedPlan(BaseModel):
    """This is the updated plan that contains all proposed changes."""

    plan: str = Field(
        description="the newly updated hierchical plan."
    )

@dataclass
class PlanFinished(BaseModel):
    """Response to user."""
    response: str

@dataclass
class PlanResult(BaseModel):
    """Action to perform."""

    action: Task = Field("Action to perform. If you want to respond to user, use Response. ")

    #action: Union[PlanFinished, Task] = Field(
    #    description="Action to perform. If you want to respond to user, use Response. "
    #    "If you need to further use tools to get the answer, use Plan."
    #)


def convert_costs_to_json(costs):
    result = costs.__dict__
    if result["prompt_tokens_details"] is not None:
        result["prompt_tokens_details"] = costs.prompt_tokens_details.__dict__
    if result["completion_tokens_details"] is not None:
        result["completion_tokens_details"] = costs.completion_tokens_details.__dict__
    return result


def llm_typed_call[T: BaseModel](
    model: str,
    api_key: str,
    messages: list[dict[str, Any]],
    id: str,
    type: Type[T] | None = None,
) -> T:
    """make a simple LLM call without any response format parsing"""

    tik = datetime.datetime.now()
    response = litellm.completion(
        model=model,
        messages=messages,
        api_key=api_key,
        response_format=type,
    )
    tok = datetime.datetime.now()

    if len(response.choices) != 1:
        raise RuntimeError(f"Expected exactly one LLM choice, but got {len(response.choices)}.")

    # output tokens costs
    costs = convert_costs_to_json(response.usage)
    duration = (tok - tik).total_seconds()

    if type is not None:
        result = type.model_validate_json(response.choices[0].message.content)
        content = asdict(result)
        return result, duration, costs
    else:
        result = response.choices[0].message
        content = {
            "content": result.content,
            "reasoning_content": result.reasoning_content
            if hasattr(result, "reasoning_content")
            else None,
        }
        return content, duration, costs


TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PLAN_UPDATE = (TEMPLATE_DIR / "ptt_update.md.jinja2").read_text()
PLAN_NEXT_STEP = (TEMPLATE_DIR / "ptt_next.md.jinja2").read_text()

class PlanTestTreeStrategy:

    plan: str = ''
    logger: Logger
    scenario: str

    def __init__(self, model, model_api_key, scenario, logger, plan=None):
        self.model = model
        self.model_api_key = model_api_key
        self.scenario = scenario
        self.logger = logger
        self.plan = plan


    def create_initial_plan(self) -> UpdatedPlan:
        target_plan = ''

        input = {
            'user_input': self.scenario,
            'plan': target_plan,
            'last_task': None,
            'summary': '',
            'knowledge': '',
        }

        prompt = Template(PLAN_UPDATE).render(input)
        history = [
            {"role": "system", "content": self.scenario},
            {"role": "user", "content": prompt}
        ]

        result, duration, costs = llm_typed_call(
            self.model,
            self.model_api_key,
            history,
            "planner_initial_plan",
        )

        self.plan = result["content"]
        print(str(costs))

        self.logger.write_llm_call('strategy_update', 
                                   prompt,
                                   result['content'],
                                   costs,
                                   duration)

    def set_new_plan(self, new_plan: str) -> None:
        """ Replace and Update the current plan with a new plan that incorporates all the new information.

        Parameters
        ----------
        new_plan : str
            The new plan that should replace the current plan.
        """
        self.plan = new_plan

    def select_next_task(self, knowledge) -> PlanResult:

        input = {
            'user_input': self.scenario,
            'plan': self.plan,
            'knowledge': knowledge
        }

        prompt = Template(PLAN_NEXT_STEP).render(input)
        history = [
            {"role": "system", "content": self.scenario},
            {"role": "user", "content": prompt}
        ]

        result, duration, costs = llm_typed_call(
            self.model,
            self.model_api_key,
            history,
            "planner_initial_plan",
            PlanResult
        )

        print(str(costs))
        if isinstance(result.action, PlanFinished):
            self.logger.write_llm_call('strategy_finished', 
                                       prompt, 
                                       result.action.response,
                                       costs,
                                       duration)
        else:
            self.logger.write_llm_call('strategy_next_task', 
                                       prompt,
                                       {
                                            'next_step': result.action.next_step,
                                            'next_step_context': result.action.next_step_context
                                       },
                                       costs,
                                       duration)
        return result
    
    def get_plan(self) -> str:
        return self.plan
