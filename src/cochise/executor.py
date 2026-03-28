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

    # TODO: we could actually capture stdout/stderr separately here, as well as finished
    return {
        'tool': tool_name,
        'cmd': args['command'] if 'command' in args else tool_name,
        'finished': True,
        'result': result,
        'tool_call_id': id
    }

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
PROMPT = (TEMPLATE_DIR / "executor_prompt.md.jinja2").read_text()
MAX_ROUNDS:int=10

class ExecutorFactory:
    def __init__(self, model, api_key, scenario, configured_tools, logger, console):
        self.model = model
        self.api_key = api_key
        self.logger = logger
        self.scenario = scenario
        self.console = console
        self.configured_tools = configured_tools

    def build(self, system_knowledge):
        return Executor(self.model, self.api_key, self.scenario, self.configured_tools, system_knowledge, self.console, self.logger)

class Executor:

    def __init__(self, model, api_key, scenario, configured_tools, system_knowledge, console, logger):
        self.model = model
        self.api_key = api_key
        self.logger = logger
        self.scenario = scenario
        self.console = console
        self.system_knowledge = system_knowledge
        self.configured_tools = configured_tools


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

        self.console.log("Starting task: " + next_step)
        self.console.print(Panel(next_step_context, title=f"Task: {next_step}"))
        self.console.print(Panel(self.system_knowledge.get_knowledge(), title="Existing Knowledge"))

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

            with self.console.status("[bold green]executor: thinking") as status:
                response_message, costs, duration = llm_tool_call(
                    self.model,
                    self.api_key,
                    tools,
                    history
                )
                
                history.append(message_to_json(response_message))

            self.logger.write_llm_call('executor_next_cmds', prompt='',
                                result={
                                    'content': response_message.content,
                                    'tool_calls': response_message.tool_calls
                                },
                                costs=costs,
                                duration=duration)
            self.console.log(str(costs))

            if is_tool_call(response_message):

                tasks = []
                display = {}

                with Progress(SpinnerColumn(),
                            TextColumn("[progress.description]{task.description}"),
                            BarColumn(),
                            TimeElapsedColumn(),
                            console=self.console
                            ) as progress:
                    
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)

                        if 'command' in args:
                            cmd = args['command']
                        else:
                            cmd = function_name

                        display[tool_call.id] = progress.add_task(f"[bold green]Executing `{cmd}`", total=100)
                        tasks.append(asyncio.create_task(perform_tool_call(tool_call.id, function_name, tools.get_function(function_name), args)))

                    for done in asyncio.as_completed(tasks):
                        result = await done

                        task_id = display[result['tool_call_id']]
                        progress.update(task_id, advance=100)
                        progress.console.print(Panel(result['result'], title=f"Tool Result for {result['cmd']}"), markup=False)
                        self.logger.write_executor_tool_call('executor_cmd', result['cmd'], '?', result['result'])
                        history.append({
                            "tool_call_id": result['tool_call_id'],
                            "role": "tool",
                            "name": result['tool'],
                            "content": result['result'],
                        })
            else:
                history.append({
                    "role": "user",
                    "content": "please continue" 
                })
                # the AI message has not tool_call -> this was some sort of result then
                if response_message.content == '':
                    self.console.log(str(response_message))
                    self.console.log("Empty response from executor LLM.. retrying")
                else:
                    summary = response_message.content
                    break
            round = round + 1

        if summary is None:
            # create new summary based on history
            history.append(
                { "role": "user", "content": "provide a summary including all findings for the high level strategy component." }
            )

            result, duration, costs = llm_typed_call(
                self.model,
                self.api_key,
                history,
                "executor_no_summary",
            ) 
            self.logger.write_llm_call('executor_no_summary', prompt='',
                    result=result,
                    costs=costs,
                    duration=duration)
            self.console.log(str(costs))

            self.console.log("result: " + str(result))
            summary = result["content"]

        print(f"summary: {summary}")
        return summary + "\n\n\n" + knowledge.get_knowledge(), knowledge
