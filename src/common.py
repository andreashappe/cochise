import os
from typing import List

from pydantic import BaseModel, Field

def get_or_fail(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"Environment variable {name} not set")
    return value

class Task(BaseModel):
    """Next Task to execute and analyze"""

    next_step: str = Field(
        description = "The next task to perform."
    )

    next_step_context: str = Field(
        description = "Concise Context for worker that executes the next step. Can be formated as a markdown list."
    )

class InvalidCommand(BaseModel):
    """This describes a command that was not executed successfully due to a parameter error."""

    command: str = Field(
        description="The command that was not executed successfully."
    )

    problem: str = Field(
        description="The problem that occured during execution."
    )

    fixed_command: str = Field(
        description="An example how the command should be correctly executed."
    )


class AnalyzedExecution(BaseModel):
    """This contains all findings such as missed opportunities, gathered facts, etc. from the current task-solving run."""

    summary: str = Field(
        description="Overall technical summary of the analyed operation."
    )

    findings: List[str] = Field(
        description = "A list of gathered findings/facts. These may related to the task but this is not required."
    )

    leads: List[str] = Field(
        description = "A list of concrete leads derived from the execution of the commands. The leads may be related to the task but this is not required." 
    )

    invalid_commands: List[InvalidCommand] = Field(
        description = "A list of commands that were not executed successfully. This may be due to a parameter error or a timeout."
    )