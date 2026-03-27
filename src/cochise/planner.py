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

        #self.logger.write_llm_call('strategy_update', 
        #                            prompt,
        #                            result['content'],
        #                            costs,
        #                            duration)
        return plan
    
    async def engage(self) -> None:
        """Engage the planner to select the next task to perform based on the current plan and knowledge. This will be called in a loop until the overall objective is achieved.
        """

        knowledge = Knowledge()

        # create an initial plan and select the first task 
        with self.console.status("[bold green]llm-call: creating initial plan and selecting next task") as status:
            plan = self.create_initial_plan()
            self.console.print(Panel(plan, title="Initial Plan"))

        # NOTE/TODO: using "until you have compromised all domains" would trigger ethical filtering with gemini-3-flash-lite
        history = [
            { "role": "system", "content": self.scenario },
            { "role": "assistant", "content": f"# Initial Plan\n\n{plan}" },
            #{ "role": "user", "content": f"don't stop until you have become domain admin for all domains! Note down findings." }, # triggers refuals
            #{ "role": "user", "content": PROMPT }
        ]


        while(True):

            self.console.print(Panel(Pretty(history)))
            # TODO: add revise-prompt somehwere here to allow the planner to revise the plan based on the current state of knowledge and previous attempts to execute tasks. This can help to overcome potential issues with the initial plan and adapt to new information that was not available when the initial plan was created.

            # prepare new executor for this round. This should signalize that the executor
            # always starts from scratch and does not have any memory of previous rounds,
            # but it will have access to the updated knowledge base which it can use to solve
            # the task at hand.
            executor = self.executor_factory.build(knowledge, [])
            tool_mapping = LLMFunctionMapping([
                executor.perform_task,
                knowledge.add_compromised_account,
                knowledge.add_entity_information
            ])

            print(str(tool_mapping))

            response_message, costs, duration = llm_tool_call(
                self.model,
                self.model_api_key,
                tool_mapping,
                history
            )
            history.append(message_to_json(response_message))

            if is_tool_call(response_message):
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    self.console.print(Panel(Pretty(args), title=f"Calling tool {function_name} with arguments"))
                    function_to_call = tool_mapping.get_function(function_name)
                    print(str(function_to_call))
                    result, new_knowledge = await function_to_call(**args)

                    # add new knowledge to high-level knowledge base, this will be used in the next iteration of the loop when the LLM selects the next task to perform
                    knowledge.merge(new_knowledge)

                    self.console.print(Panel(Pretty(result), title=f"Tool Result for {function_name}"))
                    self.console.print(Panel(Pretty(new_knowledge.get_knowledge()), title="New Knowledge"))

                    history.append({
                        "role": "tool",
                        "name": function_name,
                        "content": result,
                        "tool_call_id": tool_call.id
                    })
            else:
                history.append(message_to_json(response_message))


    #print(str(response_message))


    #result = high_level_planner.select_next_task(history, knowledge)
    #print(str(result))

    # work and update the plan until we have no tasks left, i.e., the problem is solved
#    while isinstance(result.action, Task):
#
#        console.print(Panel(Pretty(history)))
#
#        task = result.action
#        console.print(Panel(f"# Next Step\n\n{task.next_step}\n\n# Context\n\n{task.next_step_context}", title=f'Next Step ({task.mitre_attack_tactic}/{task.mitre_attack_technique})'))
#        knowledge = analyzer.get_knowledge()
#        result, messages = await executor_run(SCENARIO, task, knowledge, model, api_key, tools, console, logger)
#        console.print(Panel(result, title=f'Result of executing task: {task.next_step}'))
#
#        history.append(
#            {"role": "assistant", "content": result }
#        )
#
#        #with console.status("[bold green]llm-call: analyze response and update plan") as status:
#        #    analyzer.analyze_executor(task, result, messages, high_level_planner)
#        #    try:
#        #        console.print(Panel(high_level_planner.get_plan(), title="Updated Plan"))
#        #    except Exception as e:
#        #        console.print(f"Error while printing updated plan: {e}")
#        #        console.print(high_level_planner.get_plan())
#        #
#        with console.status("[bold green]llm-call: selecting next task") as status:
#            result = high_level_planner.select_next_task(history, knowledge)
#        print(str(result))
#
#    logger.write_line(f"run-finished; result: {str(result)}")
#    console.print(Panel(Pretty(result.action), title="Hacking Run finished!"))
