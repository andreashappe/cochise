import json
import pathlib

from jinja2 import Template
from rich.panel import Panel
from rich.pretty import Pretty

from cochise.common import LLMFunctionMapping, is_tool_call, llm_tool_call, llm_typed_call, message_to_json
from cochise.knowledge import Knowledge


PROMPT="""
From all the tasks, identify those that can be performed next. Analyze those
tasks and decide which one should be performed next based on their likelihood to
achieve the objective.

Include relevant information for the selected task as its context. This includes
detailed information such as usernames, credentials, etc. You are allowed to
gather this information from throughout the whole task plan.  Do only include information
that is specific to our objective, do not generic information. Be very concise.

Note down findings and potential leads that might be relevant for future tasks.
This can include, e.g., potential attack vectors, credentials, or other information
that might be useful for future tasks. Always note down findings and potential leads,
even if they do not seem relevant for the current task at hand, as they might become
relevant for future tasks.

You can revise the plan based on new information and failed attempts to execute tasks.
This can help to overcome potential issues with the initial plan and adapt to new
information that was not available when the initial plan was created. Perform this every
3-5 rounds.
"""

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PLAN_UPDATE = (TEMPLATE_DIR / "ptt_update.md.jinja2").read_text()

class Planner:
    
    def __init__(self, model, model_api_key, scenario, executor_factory, logger, console):
        self.model = model
        self.model_api_key = model_api_key
        self.scenario = scenario
        self.executor_factory = executor_factory
        self.logger = logger
        self.console = console

    async def revise_plan(self, new_plan:str) -> str:
        """Revise the current plan based on new information and failed attempts to execute tasks. This can help to overcome potential issues with the initial plan and adapt to new information that was not available when the initial plan was created.
        
        Parameters
        ----------
        new_plan : str
        The revised plan that should be used for the next iteration of task selection and execution.
        
        Returns
        -------
        str
        The revised plan that should be used for the next iteration of task selection and execution.
        """
        self.console.print(Panel(new_plan, title="Revised Plan"))
        return new_plan

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

        result, duration, costs = llm_typed_call(
            self.model,
            self.model_api_key,
            history,
            "planner_initial_plan",
        )

        plan = result["content"]
        print(str(costs))

        self.logger.write_llm_call('planner_initial_plan', 
                                    prompt,
                                    result['content'],
                                    costs,
                                    duration)
        return plan
    
    async def engage(self) -> None:
        """Engage the planner to select the next task to perform based on the current plan and knowledge. This will be called in a loop until the overall objective is achieved.
        """

        knowledge = Knowledge()

        # create an initial plan and select the first task 
        with self.console.status("[bold green]llm-call: creating initial plan and selecting next task") as status:
            plan = self.create_initial_plan()
            self.console.print(Panel(plan, title="Initial Plan"))

        # TODO: maybe add information about how to structure the PTT here?
        history = [
            { "role": "system", "content": self.scenario },
            { "role": "user", "content": "Create me an initial plan to achieve the overall objective. Break down the overall objective into smaller tasks and subtasks. Do not include generic steps, only very specific ones that are directly relevant for achieving the overall objective. Be concise." },
            { "role": "assistant", "content": f"# Initial Plan\n\n{plan}" },
            { "role": "user", "content": PROMPT } # always finish with user prompt
        ]

        while(True):

            self.console.print(Panel(Pretty(history)))
            # TODO: add revise-prompt somewhere here to allow the planner to revise the plan based on the current state of knowledge and previous attempts to execute tasks. This can help to overcome potential issues with the initial plan and adapt to new information that was not available when the initial plan was created.
            # TODO: maybe force it to do this every x steps or after a failed attempt to execute a task?

            # prepare new executor for this round. This should signalize that the executor
            # always starts from scratch and does not have any memory of previous rounds,
            # but it will have access to the updated knowledge base which it can use to solve
            # the task at hand.
            executor = self.executor_factory.build(knowledge)
            tool_mapping = LLMFunctionMapping([
                executor.perform_task,
                self.revise_plan,
                knowledge.add_compromised_account,
                knowledge.add_entity_information
            ])

            response_message, costs, duration = llm_tool_call(
                self.model,
                self.model_api_key,
                tool_mapping,
                history
            )
            history.append(message_to_json(response_message))
            self.logger.write_llm_call('planner_task_selection', 
                                        '',
                                        response_message,
                                        costs,
                                        duration)

            if is_tool_call(response_message):
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    self.console.print(Panel(Pretty(args), title=f"Calling tool {function_name} with arguments"))
                    function_to_call = tool_mapping.get_function(function_name)
                    print(str(function_to_call))

                    raw_result = await function_to_call(**args)
                    if isinstance(raw_result, tuple):
                        result, new_knowledge = raw_result
                        knowledge.merge(new_knowledge)
                    else:
                        result = raw_result
                        new_knowledge = Knowledge()

                    self.console.print(Panel(Pretty(result), title=f"Tool Result for {function_name}"))
                    self.console.print(Panel(Pretty(new_knowledge.get_knowledge()), title="New Knowledge"))

                    history.append({
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                        "tool_call_id": tool_call.id
                    })
            else:
                self.console.print(Panel("LLM did not call a tool, but returned a message. This should not happen, because the planner should only select a task to perform and call the respective tool for that. You might want to check if the LLM is able to call tools correctly.", title="LLM Response without Tool Call"))
                self.console.print(Panel(Pretty(response_message.content), title="LLM Response Content"))
                history.append({
                    "role": "user",
                    "content": "please continue" 
                })