import datetime
import json
import pathlib

from jinja2 import Template
from rich.panel import Panel
from rich.pretty import Pretty

from cochise.common import LLMFunctionMapping, is_tool_call, llm_tool_call, llm_typed_call, message_to_json
from cochise.knowledge import Knowledge
from cochise.logger import Logger

# TODO: move this into a template
PLANNER_PROMPT="""
You are required to strategize and create a tree-structured task plan that will allow to successfully solve the objective.
Workers will follow your task plan to complete the objective, and will report after each finished task back to you.
You should use this feedback to update the task plan.

Make sure to include relevant information, e.g., compromised accounts, credentials,
and vulnerabilities, tokens, hashes, compromised systems. Also include information
about successful attacks.

When creating the task plan you must follow the following requirements:

1. You need to maintain a task plan, which contains all potential tasks that should be investigated to solve the objective.

1.1. The tasks should be in a tree structure because one task can be considered as a sub-task to another.
1.2. Display the tasks in a layer structure, such as 1, 1.1, 1.1.1, etc.

2. Initially, create an minimal plan based upon the provided information.
2.1. The plan should contain the initial 2-3 tasks that could be delegated to the worker.
2.2. You will evolve the plan over time based upon the workers' feedback.
2.3. Don't over-engineer the initial plan.

2.1. This plan should involve individual tasks, that if executed correctly will yield the correct answer.
2.2. Do not add any superfluous steps but make sure that each step has all the information
2.3. Be concise with each task description but do not leave out relevant information needed - do not skip steps.

3. Each time you receive results from the worker you should 

3.1. Analyze the results and identify information that might be relevant for solving your objective through future steps.
3.2. Add new tasks or update existing task information according to the findings.
3.2.1. You can add additional information, e.g., relevant findings, to the tree structure as tree-items too.
3.3. You can mark a task as non-relevant and ignore that task in the future. Only do this if a task is not relevant for reaching the objective anymore. You can always make a task relevant again.
3.4. You must always include the full task plan as answer. If you are working on subquent task groups, still include previous taskgroups, i.e., when you work on task `2.` or `2.1.` you must still include all task groups such as `1.`, `2.`, etc. within the answer.

Provide the hierarchical task plan as answer. Do not include a title or an appendix.
"""

# TODO: move this into a template
PROMPT="""
From all the tasks, identify those that can be performed next. Analyze those
tasks and decide which one should be performed next based on their likelihood to
achieve the objective.

Include relevant information for the selected task as its context. This includes
detailed information such as usernames, credentials, etc. You are allowed to
gather this information from throughout the whole task plan.  Do only include information
that is specific to our objective, do not generic information. Be very concise.

Note down findings and potential leads that might be relevant for future tasks.
Make sure to always include full information, i.e., always include the full hash
or token and not abbreviated ones.

You can revise the plan based on new information and failed attempts to execute tasks.
This can help to overcome potential issues with the initial plan and adapt to new
information that was not available when the initial plan was created. Perform this every
3-5 rounds.
"""

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PLAN_UPDATE = (TEMPLATE_DIR / "ptt_update.md.jinja2").read_text()

class Planner:
    
    def __init__(self, model, model_api_key, scenario, executor_factory, logger, max_runtime:int=0):
        self.model = model
        self.model_api_key = model_api_key
        self.scenario = scenario
        self.executor_factory = executor_factory
        self.logger = logger
        self.max_runtime = max_runtime
    
    def create_initial_plan(self) -> str:
        template_vars = {
            'user_input': self.scenario,
            'plan': '',
            'last_task': None,
            'summary': '',
            'knowledge': '',
        }

        prompt = Template(PLAN_UPDATE).render(template_vars)
        history = [
            {"role": "system", "content": self.scenario},
            {"role": "user", "content": prompt}
        ]
        self.logger.log_append_to_history(history, "manual", False)

        result, duration, costs = llm_typed_call(
            self.model,
            self.model_api_key,
            history,
            "planner_initial_plan",
        )

        plan = result["content"]
        self.logger.log_llm_call('planner_initial_plan', result=plan, costs=costs, duration=duration)

        return plan
    
    async def engage(self) -> None:
        """Engage the planner to select the next task to perform based on the current plan and knowledge. This will be called in a loop until the overall objective is achieved.
        """

        knowledge = Knowledge()

        counter = 1
        started = datetime.datetime.now()

        # create an initial plan and select the first task 
        with self.logger.console.status("[bold green]llm-call: creating initial plan and selecting next task") as status:
            plan = self.create_initial_plan()

        # TODO: maybe add information about how to structure the PTT here?
        history = [
            { "role": "system", "content": self.scenario },
            { "role": "user", "content": "Create me an initial plan to achieve the overall objective. Break down the overall objective into smaller tasks and subtasks. Do not include generic steps, only very specific ones that are directly relevant for achieving the overall objective. Be concise." },
            { "role": "assistant", "content": f"# Initial Plan\n\n{plan}" },
            { "role": "user", "content": PROMPT } # always finish with user prompt
        ]
        self.logger.log_append_to_history(history, "manual", False)

        # IDEA: I could use a progress bar to show the remaining runtime
        while( self.max_runtime == 0 or (datetime.datetime.now()- started).total_seconds() <= self.max_runtime):

            # TODO: switch to a token usage based scheme
            if counter % 5 == 0:
                msg = { "role": "user", "content": PLANNER_PROMPT }

                history.append(msg)
                self.logger.log_append_to_history(msg, "manual", False)

                result, duration, costs = llm_typed_call(
                    self.model,
                    self.model_api_key,
                    history,
                    "compact history",
                ) 

                plan = result["content"]
                self.logger.log_llm_call('compact_history', plan, costs, duration, output=True)
                self.logger.console.print(Panel(plan, title="new plan"))

                history = [
                    { "role": "system", "content": self.scenario },
                    { "role": "user", "content": "Create me an initial plan to achieve the overall objective. Break down the overall objective into smaller tasks and subtasks. Do not include generic steps, only very specific ones that are directly relevant for achieving the overall objective. Be concise." },
                    { "role": "assistant", "content": f"# Initial Plan\n\n{plan}\n\n\n # Gathered Findings\n\n{knowledge.get_knowledge()}" },
                    { "role": "user", "content": PROMPT } # always finish with user prompt
                ]
                self.logger.log_append_to_history(history, "manual", False)

            # prepare new executor for this round. This should signalize that the executor
            # always starts from scratch and does not have any memory of previous rounds,
            # but it will have access to the updated knowledge base which it can use to solve
            # the task at hand.
            executor = self.executor_factory.build(knowledge)

            # IDEA: allow the planner to decide for itself when it shall call history compaction. This is too complex for the initial prototype though.
            tool_mapping = LLMFunctionMapping([
                executor.perform_task,
                knowledge.add_compromised_account,
                knowledge.update_compromised_account,
                knowledge.add_entity_information,
                knowledge.update_entity_information
            ])

            response_message, costs, duration = llm_tool_call(
                self.model,
                self.model_api_key,
                tool_mapping,
                history
            )
            self.logger.log_llm_call('planner_task_selection', result=response_message, costs=costs, duration=duration)

            history.append(message_to_json(response_message))
            self.logger.log_append_to_history(message_to_json(response_message), "agent", output=False)

            if is_tool_call(response_message):
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    self.logger.log_tool_call(function_name, tool_call.id, args)
                    function_to_call = tool_mapping.get_function(function_name)

                    # this could be cleaner:
                    # set tool call id in the executor logger, just in case the executor is run
                    executor.setLogger(Logger(self.logger.console, tool_call.id, self.logger.logger))

                    # call the method
                    raw_result = await function_to_call(**args)

                    if isinstance(raw_result, tuple):
                        result, new_knowledge = raw_result
                        if new_knowledge.get_knowledge() != "":
                            self.logger.log_data("new knowledge", new_knowledge.get_knowledge())
                            self.logger.console.print(Panel(Pretty(new_knowledge.get_knowledge()), title="New Knowledge"))
                        knowledge.merge(new_knowledge)
                    else:
                        result = raw_result
                        new_knowledge = Knowledge()

                    self.logger.log_tool_result(function_name, tool_call.id, result)
                    msg = {
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                        "tool_call_id": tool_call.id
                    }

                    self.logger.log_append_to_history(msg, "agent", output=False)
                    history.append(msg)
            else:
                # LLM did not call a tool, but returned a message. This should not happen,
                # because the planner should only select a task to perform and call
                # the respective tool for that. You might want to check if the LLM is able
                # to call tools correctly.
                self.logger.console.print(Panel(Pretty(response_message.content), title="LLM Response Content"))
                msg = {
                    "role": "user",
                    "content": "please continue" 
                }
                self.logger.log_append_to_history(msg, "manual", output=True)
                history.append(msg)
            
            counter += 1
        
        if self.max_runtime != 0 and (datetime.datetime.now() - started).total_seconds() > self.max_runtime:
            self.logger.log_data("completed", f"Max runtime of {self.max_runtime} seconds exceeded, stopping planner loop.", output=True)