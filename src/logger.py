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

    def write_prompt(self, description, prompt):
        self.logger.info(description, prompt=prompt)
        self.file_logger.info(f"{description}\n{prompt}")

    def write_next_cmd_prompt(self, ai_msg):
        self.logger.debug("executor_next_promp", result=ai_msg.content, tool_calls=ai_msg.tool_calls, metadata=ai_msg.response_metadata)

    def write_tool_calls(self, tools):
        self.file_logger.info(f"Upcoming Tool calls:\n{tools}")

    def write_tool_summary(self, summary):
        self.file_logger.info(f"Tool call summary:\n{summary}")

    def write_tool_result(self, cmd, result):
        self.file_logger.info(f"Tool call result for {cmd}:\n{result}")

    def write_next_task(self, next_step, next_step_context):
        self.file_logger.info(f"Next Task selected!\n{next_step}\n\nContext:\n{next_step_context}")

    def write_line(self, line):
        self.logger.info(line)
        self.file_logger.info(line)
