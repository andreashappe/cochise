from dataclasses import dataclass
from typing import Union, Dict, List
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from langchain_core.prompts import PromptTemplate

PLANNER_PROMPT = """
You are given the following objective by the user:

```
{user_input}
```

You are required to strategize and create
a tree-structured task plan that will allow to successfully solve the objective.
Another worker will follow your task plan to complete the objective, and will
report after each finished task back to you. You should use this feedback to update
the task plan.

When creating the task plan you must follow the following requirements:

1. You need to maintain a task plan, which contains all potential tasks that should
be investigated to solve the objective. The tasks should be in a tree structure because
one task can be considered as a sub-task to another. 

You can display the tasks in a layer structure, such as 1, 1.1, 1.1.1, etc. Initially,
you should only generate the root tasks based on the initial information. This plan
should involve individual tasks, that if executed correctly will yield the
correct answer. Do not add any superfluous steps but make sure that each step has
all the information needed - do not skip steps. You can include relevant information
as sub-node of a task.

2. Each time you receive results from the worker you should 
2.1 Analyze the message and see identify useful key information
2.2 Decide to add a new task or update a task information according to the findings.
Only add steps to the plan that still NEED to be done.
2.3 Decide to delete a task if necessary. Do this if the task is not relevant for
reaching the objective anymore.
2.4 From all the tasks, identify those that can be performed next. Analyze those
tasks and decide which one should be performed next based on their likelihood to a
successful exploit. Identify all context information that a worker that should
perform this step needs.

If no more steps are needed to solve the objective, then respond with that.

Otherwise, return a new task-plan and the next step to execute as well as all
context information that the worker needs to execute the task.

{plan}

{last_task}
"""

### Planner component: response data-type (main type: Act)
class PlanProgressing(BaseModel):
    """Plan to follow in future"""

    steps: str = Field(
        description="the hierarchical task plan"
    )

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

    action: Union[PlanFinished, PlanProgressing] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

class PlanExecute(TypedDict):
    user_input: str     # the initial user-given objective
    plan: str           # the current task plan
    last_task: str
    last_summary: str
    history: str

@dataclass
class ExecutedTask:
    task: str
    summary: str
    cmd_history: List[Dict[str, str]]

    def history_as_string(self) -> str:
        commands = []
        for x in self.cmd_history:
            tool = x['tool']
            cmd = x['cmd']
            result = x['result'].replace("\r", '')
            commands.append(f"""
## Tool call: {tool}

```bash
$ {cmd}

{result}
```
""")
        return "\n".join(commands)
    
def plan_txt(plan):
    if plan == None or plan == '':
        return """
# You have no task plan yet, generate a new plan.
"""
    else:
        return f"""
# Your original task-plan was this:

{plan}
"""

def last_task_txt(last_task):
    if last_task == None:
        return ''
    else:
        return f"""
# You have recently executed the following command

Integrate findings and results from this commands into the task plan

## Task

{last_task.task}

## Summarized Results

{last_task.summary}

## Executed Steps

{last_task.history_as_string()}
"""

def perform_planning_step(llm, task, logger, plan=None, last_task=None):
    replanner = PromptTemplate.from_template(PLANNER_PROMPT)

    state = PlanExecute(
        user_input = task,
        plan = plan_txt(plan),
        last_task = last_task_txt(last_task)
    )
    prompt=replanner.format(user_input=task, plan=plan_txt(plan), last_task=last_task_txt(last_task))
    logger.debug("pre_planning_prompt", prompt=prompt)
    print(prompt)
    
    replanner = replanner | llm.with_structured_output(PlanResult, include_raw=True)
    result = replanner.invoke(state)
    metadata=result['raw'].response_metadata
    print(str(metadata))

    logger.debug("planning_prompt_finished", prompt=prompt, metadata=metadata)

    return result['parsed']
