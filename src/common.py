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

    mitre_attack_tactic: str = Field(
        description = "The MITRE ATT&CK tactic associated with the next step."
    )

    mitre_attack_technique: str = Field(
        description = "The MITRE ATT&CK technique associated with the next step."
    )

class AnalyzedExecution(BaseModel):
    """Analysis of an executed task which describes the overall result"""

    summary: str = Field(
        description="Overall technical summary of the analyzed operation including concrete findings."
    )

    gathered_knowledge: List[str] = Field(
        description = "A list of gathered knowledge about the target environment, e.g., usernames, password, system information, vulnerabilities."""
    )

def is_tool_call(msg) -> bool:
    return hasattr(msg, "tool_calls") and len(msg.tool_calls) > 0