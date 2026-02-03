import json
from typing import List

from rich.console import Console
from rich.pretty import Pretty
from rich.panel import Panel

from ptt import PlanTestTreeStrategy
from common import Task, is_tool_call, LLMFunctionMapping, llm_tool_call, message_to_json
from knowledge import Knowledge

MAX_ROUNDS = 10

class AgentAnalyzer:
    def __init__(self, model, api_key, console:Console, logger):
        self.model = model
        self.api_key = api_key
        self.console = console
        self.logger = logger
        self.knowledge = Knowledge()

    def get_knowledge(self) -> str:
        return self.knowledge.get_knowledge()

    def analyze_executor(self, task: Task, result:str, history:List[dict], planner: PlanTestTreeStrategy) -> None:
        # output the result, then return it
        if result!= None and len(result) > 0:
            self.console.print(Panel(result, title="ExecutorAgent Output"))
        else:
            self.console.print(Panel('no result summary provided', title="ExecutorAgent Output"))

        tools = LLMFunctionMapping([
            self.knowledge.add_compromised_account,
            self.knowledge.add_entity_information,
            planner.set_new_plan
        ])

        prompt=f"""
Update the task plan (see system message for details).

1. Each time you receive results from the worker you should 

1.1. Analyze the results and identify information that might be relevant for solving your objective through future steps.
1.2. Add new tasks or update existing task information according to the findings.
1.2.1. You can add additional information, e.g., relevant findings, to the tree structure as tree-items too.
1.3. You can mark a task as non-relevant and ignore that task in the future. Only do this if a task is not relevant for reaching the objective anymore. You can always make a task relevant again.
1.4. You must always include the full task plan as answer. If you are working on subquent task groups, still include previous taskgroups, i.e., when you work on task `2.` or `2.1.` you must still include all task groups such as `1.`, `2.`, etc. within the answer.

Initially, you should add information on identified/compromised accounts and entities.

1.1. You should add information on identified/compromised accounts and entities.
1.2. You should add information on vulnerabilities and other entities that might be relevant for a future attack.
1.3. You should add information on successful attacks and other information that might be relevant for a future attack.

Always use the `PlanUpdateTool` to update the task plan. Do not include a title or an appendix.

Make sure to note down all compromised accounts and entities and update the plan before finishing the analysis. As final answer give a summary of the changes to the task plan.
"""
        
        self.console.print(Pretty(history))

        history.append({ "role": "user", "content": prompt })

        # try to solve our sub-task
        round = 1
        while round <= MAX_ROUNDS:

            with self.console.status("[bold green]analyst: thinking") as status:

                response_message, costs, duration = llm_tool_call(
                    self.model,
                    self.api_key,
                    tools,
                    history
                )

            history.append(message_to_json(response_message))
            self.console.log(str(costs))

            self.logger.write_llm_call('analyst_next', prompt=prompt,
                                result={
                                    'content': response_message.content,
                                    'tool_calls': response_message.tool_calls
                                },
                                costs=costs,
                                duration=duration)

            if is_tool_call(response_message):
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    result = tools.get_function(function_name)(**args)

                    self.console.print(Panel(Pretty(args | {'result': result}), title=f"Tool {function_name}"))
                    history.append({
                        "role": "tool",
                        "name": function_name,
                        "content": str(result),
                         "tool_call_id": tool_call.id
                    })   
            else:
                print(str(response_message))
                content = response_message.content if response_message.content is not None else ""
                self.console.print(Panel(content, title="Summary of updates"))
                return content

            round = round + 1