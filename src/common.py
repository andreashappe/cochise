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
        description="How would you fix the problem? Give an example how the command should be correctly executed."
    )

class AnalyzedExecution(BaseModel):
    """Analysis of an executed task which describes the overall result."""

    summary: str = Field(
        description="""
        Overall technical concise summary of the analyzed operation including concrete findings.
        """
    )

    gathered_knowledge: List[str] = Field(
        description = "A list of gathered knowledge about the target environment, e.g., system information, usernames, passwords, system information, vulnerabilities."""
    )

    vulnerabilities: List[str] = Field(
        description = "Exploitable vulnerabilities that were found during the execution of the task."
    )

    potential_next_steps: List[str] = Field(
        description="What would be good next steps to execute based upon the current log trace."""
    )

    invalid_commands: List[InvalidCommand] = Field(
        description="A list of invalid commands that were not executed successfully."
    )
