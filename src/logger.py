import logging
import structlog

from datetime import datetime
from pathlib import Path

class Logger:

    logger = None
    file_logger = None

    def __init__(self):
        # setup structured logging
        current_timestamp = datetime.now()
        formatted_timestamp = current_timestamp.strftime('%Y%m%d-%H%M%S')

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

        # setup a stupid file-based logger too
        self.file_logger = logging.getLogger("my_logger")
        self.file_logger.setLevel(logging.DEBUG)

        handler = logging.FileHandler(Path(f"logs/run-{formatted_timestamp}.log"))
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.file_logger.addHandler(handler)

    def write_llm_call(self, name, prompt, result, costs, duration=-1):
        self.logger.info(name, prompt=prompt, result=result, costs=costs, duration=duration)
        self.file_logger.info(f"{name}\n{prompt}")
        self.file_logger.info(f"{name} result\n{result}")
        self.file_logger.info(f"{name} costs\n{str(costs)}\tduration: {str(duration)}")

        model = costs['model_name']
        total = costs['token_usage']['total_tokens']
        prompt = costs['token_usage']['prompt_tokens']
        completions = costs['token_usage']['completion_tokens']
        reasoning = costs['token_usage']['completion_tokens_details']['reasoning_tokens']
        cached = costs['token_usage']['prompt_tokens_details']['cached_tokens']
        print(f"{name} ({model}) costs: {total} ({prompt}/{completions}/{reasoning}/{cached}\tduration: {str(duration)}")

    def write_executor_tool_call(self, name, cmd, exit_code, result):
        self.logger.info(name, cmd=cmd, exit_code=exit_code, result=result)

    def write_tool_calls(self, tools):
        self.file_logger.info(f"Upcoming Tool calls:\n{tools}")

    def write_tool_summary(self, summary):
        self.file_logger.info(f"Tool call summary:\n{summary}")

    def write_line(self, line):
        self.logger.info(line)
        self.file_logger.info(line)
