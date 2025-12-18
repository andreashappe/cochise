import structlog

from datetime import datetime
from pathlib import Path

class Logger:

    logger = None

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

    def write_llm_call(self, name, prompt, result, costs, duration=-1):
        self.logger.info(name, prompt=prompt, result=result, costs=costs, duration=duration)

    def write_executor_tool_call(self, name, cmd, exit_code, result):
        self.logger.info(name, cmd=cmd, exit_code=exit_code, result=result)

    def write_line(self, line):
        self.logger.info(line)
