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
        description="The problem that occured during execution. Start with the basename of the involved command, followed by a ':'"
    )

    fixed_command: str = Field(
        description="An example how the command should be correctly executed."
    )


class AnalyzedExecution(BaseModel):
    """Analysis of an executed task which describes the overall result
       including relevant findings, includes a list of gathered knowledge
       of the target environment, identified vulnerabilities, as well
       as a list of invalidly used commands that happened during execution."""

    summary: str = Field(
        description="Overall technical summary of the analyzed operation. This should include concrete findings and leads."
    )

    gathered_knowledge: List[str] = Field(
        description = "A list of gathered knowledge about the target environment, e.g., usernames, password, system information, vulnerabilities."""
    )

    vulnerabilities: List[str] = Field(
        description = "A list of concrete vulnerabilities that were detected during analysis of the executed commands. This can include leads if there is concrete evidence for their exploitability. This should include detailed information howto exploit the vulnerability, e.g, an example system command to execute."""
    )

    invalid_commands: List[InvalidCommand] = Field(
        description = "A list of commands that were not executed successfully, e.g., due to invalid or non-existing parameters, unkonwn system commands, etc. This should not include commands where the parameter was formally correct, but semantically invalid (e..g, a wrong password or username was given)."""
    )