import asyncio
import json
import pathlib

from jinja2 import Template
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn,TimeElapsedColumn

from cochise.common import is_tool_call, LLMFunctionMapping, llm_tool_call, llm_typed_call, message_to_json
from cochise.knowledge import Knowledge

async def perform_tool_call(id, tool_name, function, args):
    result = await function(**args)
    return {
        'tool': tool_name,
        'cmd': args['command'] if 'command' in args else tool_name,
        'result': result['output'] if isinstance(result, dict) and 'output' in result else str(result),
        'exit_status': result['exit_status'] if isinstance(result, dict) and 'exit_status' in result else None,
        'tool_call_id': id
    }

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PROMPT = (TEMPLATE_DIR / "executor_prompt.md.jinja2").read_text()
MAX_ROUNDS:int=10

class ExecutorFactory:
    def __init__(self, model, api_key, scenario, configured_tools, logger):
        self.model = model
        self.api_key = api_key
        self.logger = logger
        self.scenario = scenario
        self.configured_tools = configured_tools

    def build(self, system_knowledge):
        return Executor(self.model, self.api_key, self.scenario, self.configured_tools, system_knowledge, self.logger)

class Executor:

    def __init__(self, model, api_key, scenario, configured_tools, system_knowledge, logger):
        self.model = model
        self.api_key = api_key
        self.logger = logger
        self.scenario = scenario
        self.system_knowledge = system_knowledge
        self.configured_tools = configured_tools

    def setLogger(self, logger):
        self.logger = logger

    async def perform_task(self, next_step: str, next_step_context: str, mitre_attack_tactic: str, mitre_attack_technique: str) -> str:
        """Perform the given task, which is a sub-task of the overall hacking objective.

        Parameters
        ----------
        next_step : str
            The next step to perform.
        next_step_context : str
            Concise Context for worker that executes the next step. Can be formated as a markdown list.
        mitre_attack_tactic : str
            The MITRE ATT&CK tactic associated with the next step.
        mitre_attack_technique : str
            The MITRE ATT&CK technique associated with the next step.

        Returns 
        -------
        str
            A summary of the performed task, including any relevant findings.
        """

        self.logger.log_data("executor", "Starting task: " + next_step)
        if self.system_knowledge.get_knowledge() != "":
            self.logger.console.print(Panel(self.system_knowledge.get_knowledge(), title="Existing Knowledge"))

        prompt = Template(PROMPT).render({
            'next_step': next_step,
            'next_step_context': next_step_context,
            'max': str(MAX_ROUNDS-1),
            'knowledge': self.system_knowledge.get_knowledge()
        })
            
        history = [
            { "role": "system", "content": self.scenario },
            { "role": "user", "content": prompt + "\n\n\n" + 'always note down findings and potential leads' },
        ]
        self.logger.log_append_to_history(history, source='manual', output=False)

        knowledge = Knowledge()
        tools = LLMFunctionMapping(self.configured_tools + [
            knowledge.add_compromised_account,
            knowledge.update_compromised_account,
            knowledge.add_entity_information,
            knowledge.update_entity_information
        ])

        # try to solve our sub-task
        round = 1
        summary = None
        while round <= MAX_ROUNDS:

            with self.logger.console.status("[bold green]executor: thinking"):
                response_message, costs, duration = llm_tool_call(
                    self.model,
                    self.api_key,
                    tools,
                    history
                )
                self.logger.log_llm_call('executor_next_cmds', response_message, costs, duration, output=True)
                
                self.logger.log_append_to_history(response_message, source='agent', output=False)
                history.append(message_to_json(response_message))

            if is_tool_call(response_message):

                tasks = []
                display = {}

                with Progress(SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TimeElapsedColumn(),
                            console=self.logger.console
                            ) as progress:
                    
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)

                        if 'command' in args:
                            cmd = args['command']
                        else:
                            cmd = function_name

                        display[tool_call.id] = progress.add_task(f"[bold green]Executing `{cmd}`", total=100)
                        self.logger.log_tool_call(function_name, tool_call.id, args, output=True)
                        tasks.append(asyncio.create_task(perform_tool_call(tool_call.id, function_name, tools.get_function(function_name), args)))

                    for done in asyncio.as_completed(tasks):
                        result = await done

                        task_id = display[result['tool_call_id']]

                        progress.update(task_id, advance=100)
                        progress.console.print(Panel(result['result'], title=f"Tool Result for {result['cmd']}"), markup=False)
                        self.logger.log_tool_result(result['tool'],result['tool_call_id'], result['result'], output=True)

                        # IDEA: when executing commands, we get an exit-code, use this to
                        # IDEA: to detect errors.
                        msg = {
                            "tool_call_id": result['tool_call_id'],
                            "role": "tool",
                            "name": result['tool'],
                            "content": result['result'],
                        }
                        history.append(msg)
                        self.logger.log_append_to_history(msg, source='agent', output=False)
            else:
                # the AI message has not tool_call -> this was some sort of result then
                if response_message.content == '':
                    msg = {
                        "role": "user",
                        "content": "please continue" 
                    }
                    history.append(msg)
                    self.logger.log_append_to_history(msg, source='manual', output=True)

                    self.logger.console.log(str(response_message))
                    self.logger.console.log("Empty response from executor LLM.. retrying")
                else:
                    summary = response_message.content
                    break
            round = round + 1

        if summary is None:
            # create new summary based on history
            msg = { "role": "user", "content": "provide a summary including all findings for the high level strategy component." }

            history.append(msg)
            self.logger.log_append_to_history(msg, source='manual', output=False)

            result, duration, costs = llm_typed_call(
                self.model,
                self.api_key,
                history,
                "executor_no_summary",
            ) 
            self.logger.log_llm_call('executor_no_summary', result, costs, duration, output=True)
            summary = result["content"]

        return summary + "\n\n\n" + knowledge.get_knowledge(), knowledge
