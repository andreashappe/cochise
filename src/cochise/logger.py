import structlog

from types import NoneType

from litellm import Message
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

from datetime import datetime
from pathlib import Path

from cochise.common import message_to_json

class Logger:

    logger:structlog.WriteLogger
    identity:str

    def __init__(self, console:Console, identity:str='main', logger=None):

        self.console = console

        if identity is not None and logger is not None:
            # this happens for sub-loggers
            self.identity = identity
            self.logger = logger
        else:
            self.identity = identity

            # setup structured logging
            current_timestamp = datetime.now()
            formatted_timestamp = current_timestamp.strftime('%Y%m%d-%H%M%S')

            # crate log directory if it doesn't exist
            Path("logs").mkdir(exist_ok=True)

            structlog.configure(
                processors=[
                    structlog.processors.add_log_level,
                    structlog.processors.StackInfoRenderer(),
                    structlog.dev.set_exc_info,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer(),
                ],
                logger_factory=structlog.WriteLoggerFactory(
                    file=Path(f"logs/run-{formatted_timestamp}").with_suffix(".json").open("wt")
                )
            )

            self.logger = structlog.get_logger()

    def log_data(self, name:str, data:str|dict|NoneType=None, output:bool=True) -> None:
        if isinstance(data, dict):
            if output:
                tmp = "\n".join([f"{k}: {v}" for k, v in data.items()])
                self.console.print(Panel(tmp, title=name))
            self.logger.info(name, agent=self.identity,**data) # ty: ignore[unknown-argument]
        elif isinstance(data, NoneType):
            if output:
                self.console.log(name)
            self.logger.info(name, agent=self.identity) # ty: ignore[unknown-argument]
        elif isinstance(data, str):
            if output:
                self.console.log(f"{name}: {data}")
            self.logger.info(name, content=data, agent=self.identity) # ty: ignore[unknown-argument]
        else:
            raise Exception(f"unsupported data type for logging {data}")

    def log_llm_call(self, name:str, result, costs: dict, duration:float, output:bool=True) -> None:

        if isinstance(result, Message):
            result = message_to_json(result)

        self.logger.info("llm_call", name=name, costs=costs, duration=duration, result=result, agent=self.identity) # ty: ignore[unknown-argument]
        if output:
            # IDEA: make this prettier in the future and maybe add accounting?
            # IDEA: maybe also only output costs/accumulated costs?
            if isinstance(result, dict):
                result = Pretty(result)

            cost_str = f"Tokens: {costs['total_tokens']} (prompt: {costs['prompt_tokens']}, cached: {costs['prompt_tokens_details']['cached_tokens']}, completion: {costs['completion_tokens']}), Cost: ${costs['cost']:.4f}, Duration: {duration:.2f}s"
            self.console.print(Panel(result, title=f"LLM Call Result for {name}", subtitle=cost_str))

    def log_history_item(self, entry, source, output) -> None:
        if isinstance(entry, Message):
            entry = message_to_json(entry)
        self.logger.info("history_append", source=source, content=entry, agent=self.identity) # ty: ignore[unknown-argument]
        if output:
            self.console.print(Panel(Pretty(entry), title=f"Appended ({source.capitalize()}) Message To History"))

    # IDEA: source can be 'manual' or 'agent' to signalize whether this was a manual log or agent generated
    def log_append_to_history(self, entry, source:str='manual', output:bool=True) -> None:
        if isinstance(entry, list):
            for itm in entry:
                self.log_history_item(itm, source, output)
        else:
            self.log_history_item(entry, source, output)
    
    def log_tool_call(self, name:str, tool_call_id:str, params, output:bool=True) -> None:
        self.logger.info("tool_call", tool_name=name, tool_call_id=tool_call_id, params=params, agent=self.identity) # ty: ignore[unknown-argument]

        if output:
            self.console.print(Panel(Pretty(params), title=f"Calling tool {name} with arguments"))

    def log_tool_result(self, name:str, tool_call_id:str, result, output:bool=True) -> None:
        self.logger.info("tool_result", tool_name=name, tool_call_id=tool_call_id, result=result, agent=self.identity) # ty: ignore[unknown-argument]

        if output:
            self.console.print(Panel(Pretty(result), title=f"Tool Result for {name}"))
        
