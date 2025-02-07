#!/usr/bin/python3

import json
import xlsxwriter

from pathlib import Path
from rich.console import Console
from rich.pretty import Pretty

import openai
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from common import get_or_fail
from dotenv import load_dotenv

console = Console()
# setup API keys
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
llm = ChatOpenAI(model="gpt-4o", temperature=0)

files = [
    #'examples/test-runs/initial-setup/run-20250128-181630.json',
    #'examples/test-runs/first-round/run-20250128-203002.json',
    #'examples/test-runs/first-round/run-20250129-152651.json',

    # 'examples/test-runs/first-round/run-20250129-074136.json', # just one hour
    #'examples/test-runs/first-round/run-20250129-172241.json', # just one hour

    #'examples/test-runs/first-round/run-20250129-085237.json',
    #'examples/test-runs/first-round/run-20250129-194248.json',
    'examples/test-runs/first-round/run-20250129-110006.json'

]


class CmdResult(BaseModel):
    """Analyze the given command and its result"""

    command_produced_usable_output: bool = Field(
            description="Even while the command execution produced an error, results were relevant for security analysis."
    )

    invalid_parameter: bool = Field(
            description="The given command produced an error and terminated due to an invalid parameter given to the command."
    )

    executable_unknown: bool = Field(
            description="The given command did not exist on the target system."
    )

    other_error: bool = Field(
            description="The given command did produce an error that was not related to invalid parameters given through the command line."
    )

def tool_call_analysis(cmd:str, result:str) -> CmdResult:
    prompt = PromptTemplate.from_template("""You were given the following command to execute:

    `{cmd}`

    Exeuction of the command produced the following console output:

    ```
    {result}
    ```

    Analyze if the command was executed succesfully or if invocation produced an error.
    Differentiate between errors that were produced due to invalid parameters given (for example if the command misses mandatory parameters, or if a non-existing option was used, or if a parameter had the wrong format) and other errors.
    """).format(cmd=cmd, result=result)

    result = llm.with_structured_output(CmdResult).invoke(prompt)
    console.print(Pretty(result))
    return result


tools = {}
invalid_toolcalls_per_run = {}

def analyze_file(filename):
    with open(filename, 'r') as file:

        xslx_path = f"{Path(filename).stem}_executed_commands.xlsx"

        print(f"Writing output into {xslx_path}")

        workbook = xlsxwriter.Workbook(xslx_path)
        worksheet = workbook.add_worksheet()
        row = 1

        worksheet.write_row(0, 0, ['CMD', 'CLI', 'Result', 'usable_output', 'invalid_paramter', 'exeuctable_unknown', 'other_error'])
        for line in file:
            j = json.loads(line)

            if j['event'] == 'executor_cmd':
                cli = j['cmd']
                result = j['result']
                cmd = j['cmd'].split(' ')[0]

                console.print(Pretty({
                        'cli': cli,
                        'cmd': cmd,
                        'result': result
                    }
                ))

                try:
                    answer = tool_call_analysis(cli, result)
                    worksheet.write_row(row, 0, [cmd, cli, result,
                                                answer.command_produced_usable_output,
                                                answer.invalid_parameter,
                                                answer.executable_unknown,
                                                answer.other_error])
                except openai.BadRequestError:
                    worksheet.write_row(row, 0, [cmd, cli, result])

                row += 1

        workbook.close()

for file in files:
    analyze_file(file)