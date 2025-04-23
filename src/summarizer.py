import datetime
import pathlib
from typing import List

from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common import Task

TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
TEMPLATE_RESULT = PromptTemplate.from_file(str(TEMPLATE_DIR / 'summarizer.md.jinja2'), template_format='jinja2')

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

    gathered_knowledge: str = Field(
        description = "Gathered knowledge about the target environment, e.g., system information, usernames, passwords, system information, vulnerabilities."""
    )

    potential_next_steps: List[str] = Field(
        description="What would be good next steps to execute based upon the current log trace."""
    )

    invalid_commands: List[InvalidCommand] = Field(
        description="A list of invalid commands that were not executed successfully."
    )

def summarize(console, llm, logger, SCENARIO:str, task:Task, history):

    input = {
            'SCENARIO': SCENARIO,
            'task': task,
            'history': history
    }

    # try to get a list of findings (disabled for now)
    summarizer = TEMPLATE_RESULT| llm.with_structured_output(AnalyzedExecution, include_raw=True)

    tik = datetime.datetime.now()
    result = summarizer.invoke(input)
    tok = datetime.datetime.now()

    analyzed = result['parsed']

    logger.write_llm_call('summarizer', prompt='',
                      result=analyzed,
                      costs=result['raw'].response_metadata,
                      duration=(tok-tik).total_seconds())
    console.log("Finished low-level executor run..")

    return analyzed.gathered_knowledge, analyzed.potential_next_steps, analyzed.invalid_commands