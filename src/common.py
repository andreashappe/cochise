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
        description = "A list of exploited or concrete vulnerabilties or missconfigurations that occurred during task execution. This can include concrete informaiton (such as credentials or tokens) that could be abused during future steps. This can include leads if there is concrete evidence for their exploitability."""
    )

    potential_next_steps: List[str] = Field(
        description="What would be good next steps to execute based upon the current log trace. If possible, give concrete commands that could be executed."""
    )