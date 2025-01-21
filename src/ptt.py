from typing import Union
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

# Your original task-plan was this:

{plan}

# You have recently executed the following command

Integrate findings and results from this commands into the task plan

## Task

{last_task}

## Summarized Results

{last_summary}

## Executed Steps

{history}
"""

### Planner component: response data-type (main type: Act)
class Plan(BaseModel):
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

class Response(BaseModel):
    """Response to user."""
    response: str

class Act(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )

class PlanExecute(TypedDict):
    user_input: str     # the initial user-given objective
    plan: str           # the current task plan
    last_task: str
    last_summary: str
    history: str

def perform_planning_step(llm, task, plan, last_task, logger):
    replanner = PromptTemplate.from_template(PLANNER_PROMPT)

    state = PlanExecute(
        user_input = task,
        plan = plan,
        history = last_task.history_as_string(),
        last_task = last_task,
        last_summary = last_task.summary
    )
    prompt=replanner.format(user_input=task, plan=state['plan'], last_task=state["last_task"], last_summary=state["last_summary"], history=state["history"])
    logger.debug("planning_prompt", prompt=prompt)
    print(prompt)
    
    replanner = replanner | llm.with_structured_output(Act)

    return replanner.invoke(state)

def perform_initial_step(llm, task, logger):
    replanner = PromptTemplate.from_template(PLANNER_PROMPT)

    state = PlanExecute(
        user_input = task,
        plan = 'no plan yet',
        history = "nothing executed yet",
        last_task = "no task selected yet",
        last_summary = "nothing executed yet"
    )

    print(str(state))

    prompt=replanner.format(user_input=task, plan=state['plan'], last_task=state["last_task"], last_summary=state["last_summary"], history=state["history"])
    logger.debug("planning_prompt", prompt=prompt)
    print(prompt)
    
    replanner = replanner | llm.with_structured_output(Act)

    return replanner.invoke(state)