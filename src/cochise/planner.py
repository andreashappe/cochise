import datetime
import json
import pathlib

from rich.markdown import Markdown
from rich.panel import Panel
from rich.pretty import Pretty

from cochise.common import LLMFunctionMapping, is_tool_call, llm_call, llm_tool_call, message_to_json
from cochise.knowledge import Knowledge
from cochise.logger import Logger

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"

PLANNER_STRUCTURE = (TEMPLATE_DIR / "planner_structure.md").read_text()
PROMPT = (TEMPLATE_DIR / "planner_prompt.md").read_text()

class Planner:
    
    def __init__(self, model, model_api_key, scenario, executor_factory, logger, max_runtime:int=0, max_context_size:int=0, max_interactions:int=0):
        self.model = model
        self.model_api_key = model_api_key
        self.scenario = scenario
        self.executor_factory = executor_factory
        self.logger = logger
        self.max_runtime = max_runtime
        self.max_context_size = max_context_size
        self.max_interactions = max_interactions

        self.history = []
        self.knowledge = Knowledge(self.logger)

    # IDEA: unify with compact_history
    def create_initial_plan(self) -> str:
        tmp_history = [
            {"role": "system", "content": self.scenario},
            {"role": "user",   "content": PLANNER_STRUCTURE + "\n\n# Task\n\nProvide the hierarchical task plan as answer. Do not include a title or an appendix." }
        ]
        self.logger.log_append_to_history(tmp_history, "manual", False)

        result, duration, costs = llm_call(self.model, self.model_api_key, tmp_history)

        plan = result["content"]
        self.logger.log_llm_call('planner_initial_plan', result=plan, costs=costs, duration=duration)

        return plan
    
    def compact_history(self) -> None:
        msg = { "role": "user", "content": PLANNER_STRUCTURE + "\n\n# Task\n\nProvide the hierarchical task plan as answer. Do not include a title or an appendix." }

        self.history.append(msg)
        self.logger.log_append_to_history(msg, "manual", False)

        result, duration, costs = llm_call(self.model, self.model_api_key, self.history)

        plan = result["content"]
        self.logger.log_llm_call('compact_history', plan, costs, duration, output=True)
        self.logger.console.print(Panel(plan, title="new plan"))

        self.history = [
            { "role": "system", "content": self.scenario + "\n\n# Task Plan Creation and Evolution\n\n" + PLANNER_STRUCTURE },
            { "role": "user", "content": "Create me an initial plan to achieve the overall objective. Break down the overall objective into smaller tasks and subtasks. Do not include generic steps, only very specific ones that are directly relevant for achieving the overall objective. Be concise." },
            { "role": "assistant", "content": f"# Initial Plan\n\n{plan}\n\n\n # Gathered Findings\n\n{self.knowledge.get_knowledge()}" },
            { "role": "user", "content": PROMPT } # always finish with user prompt
        ]
        self.logger.log_append_to_history(self.history, "manual", False)

    async def handle_tool_calls(self, response_message, executor, tool_mapping):
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            self.logger.log_tool_call(function_name, tool_call.id, args, output=False)
            function_to_call = tool_mapping.get_function(function_name)

            # this could be cleaner:
            # set tool call id in the executor logger, just in case the executor is run
            executor.setLogger(Logger(self.logger.console, tool_call.id, self.logger.logger))

            # call the method
            raw_result = await function_to_call(**args)

            if isinstance(raw_result, tuple):
                result, new_knowledge = raw_result
                # IDEA: summary (result) often has a new plan, maybe use that explicitly?
                new_knowledge_str = new_knowledge.get_knowledge()
                if new_knowledge_str != "":
                    self.logger.log_data("new knowledge", new_knowledge_str, output=False)
                    self.logger.console.print(Panel(Markdown(new_knowledge_str), title="New Knowledge"))
                self.knowledge.merge(new_knowledge)
            else:
                result = raw_result
                new_knowledge = Knowledge(self.logger)

            self.logger.log_tool_result(function_name, tool_call.id, result, output=False)
            msg = {
                "role": "tool",
                "name": function_name,
                "content": result,
                "tool_call_id": tool_call.id
            }

            self.logger.log_append_to_history(msg, "agent", output=False)
            self.history.append(msg)

    
    async def engage(self) -> None:
        """Engage the planner to select the next task to perform based on the current plan and knowledge. This will be called in a loop until the overall objective is achieved.
        """

        # used for stopping and compaction logic
        interaction_counter = 0 # this is currently a round-counter actually
        last_input_tokens = 0
        started = datetime.datetime.now()

        # create an initial plan and select the first task 
        with self.logger.console.status("[bold green]llm-call: creating initial plan"):
            plan = self.create_initial_plan()

        self.history = [
            { "role": "system", "content": self.scenario + "\n\n# Task Plan Creation and Evolution\n\n" + PLANNER_STRUCTURE },
            { "role": "user", "content": "Create me an initial plan to achieve the overall objective. Break down the overall objective into smaller tasks and subtasks. Do not include generic steps, only very specific ones that are directly relevant for achieving the overall objective. Be concise." },
            { "role": "assistant", "content": f"# Initial Plan\n\n{plan}" },
            { "role": "user", "content": PROMPT } # always finish with user prompt
        ]
        self.logger.log_append_to_history(self.history, "manual", False)

        # IDEA: I could use a progress bar to show the remaining runtime
        # IDEA: I could also output the currently used context size
        while( self.max_runtime == 0 or (datetime.datetime.now()- started).total_seconds() <= self.max_runtime):

            # IDEA: do we even need the max-interaction based compaction?
            # IDEA: give the planner the option to trigger compaction itself by calling a tool
            if self.max_interactions != 0 and interaction_counter >= self.max_interactions or self.max_context_size != 0 and last_input_tokens >= self.max_context_size:
                self.logger.log_data("compaction-triggered", f"Starting compaction to prevent excessive resource usage. Interaction count: {interaction_counter}, last input token count: {last_input_tokens}", output=True)
                self.compact_history()

            # prepare new executor for this round. This should signalize that the executor
            # always starts from scratch and does not have any memory of previous rounds,
            # but it will have access to the updated knowledge base which it can use to solve
            # the task at hand.
            executor = self.executor_factory.build(self.knowledge)

            tool_mapping = LLMFunctionMapping([
                executor.perform_task,
                self.knowledge.add_compromised_account,
                self.knowledge.update_compromised_account,
                self.knowledge.add_entity_information,
                self.knowledge.update_entity_information
            ])

            # TODO: we need some error handling here (in case of misformed tool calls)
            with self.logger.console.status("[bold green]llm-call: select next task to perform"):
                response_message, costs, duration = llm_tool_call(
                    self.model,
                    self.model_api_key,
                    tool_mapping,
                    self.history
                )
            self.logger.console.log("LLM call completed, processing response...")
            self.logger.log_llm_call('planner_task_selection', result=response_message, costs=costs, duration=duration, output=False)
            last_input_tokens = costs['prompt_tokens']

            self.history.append(message_to_json(response_message))
            self.logger.log_append_to_history(message_to_json(response_message), "agent", output=False)

            # IDEA: unify planner and executor tool call handling
            if is_tool_call(response_message):
                await self.handle_tool_calls(response_message, executor, tool_mapping)
            else:
                # TODO: check if we're really done and exit

                # LLM did not call a tool, but returned a message. This should not happen,
                # because the planner should only select a task to perform and call
                # the respective tool for that. You might want to check if the LLM is able
                # to call tools correctly.
                self.logger.console.print(Panel(Pretty(response_message.content), title="LLM Response Content"))
                msg = {
                    "role": "user",
                    "content": "You MUST call the perform_task tool to delegate work to the executor. Select the most promising incomplete task from the plan and call perform_task with it now."
                }
                self.logger.log_append_to_history(msg, "manual", output=True)
                self.history.append(msg)
            
            interaction_counter += 1
        
        if self.max_runtime != 0 and (datetime.datetime.now() - started).total_seconds() > self.max_runtime:
            self.logger.log_data("completed", f"Max runtime of {self.max_runtime} seconds exceeded, stopping planner loop.", output=True)