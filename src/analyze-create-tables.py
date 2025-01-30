#!/usr/bin/python3

import json
import sys
import xlsxwriter

from dotenv import load_dotenv

from rich.console import Console
from rich.pretty import Pretty

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pathlib import Path
from pydantic import BaseModel, Field

from common import get_or_fail

console = Console()

class CmdResult(BaseModel):
    """Analyze the given command and its result"""

    wrong_format: bool = Field(
            description="The executed command had an invalid parameter and execution was aborted"
    )

    executable_unknown: bool = Field(
            description="The executed command did not exist on the target system."
    )

    successful: bool = Field(
            description="The executed command was successful."
    )

    tactic: str = Field(
            description="This command matches this MITRE ATT&CK tactic"
    )

    technique: str = Field(
            description="This command matches this MITRE ATT&CK technique"
    )

class Task(BaseModel):
    """Analyze the given task"""

    tactic: str = Field(
            description="This command matches this MITRE ATT&CK tactic"
    )

    technique: str = Field(
            description="This command matches this MITRE ATT&CK technique"
    )

    successful: bool = Field(
            description="Does the task result imply that the task was concluded successfully?"
    )

# setup API keys
load_dotenv()
get_or_fail("OPENAI_API_KEY") # langgraph will use this env variable itself
llm = ChatOpenAI(model="gpt-4o", temperature=0)

def analyze_task(task, context, result, cmds):
    prompt = PromptTemplate.from_template("""You are given the following task:

    `{task}`

    and this context:

    ```
    {context}
    ```

    The task result was:

    ```
    {result}
    ```
    
    The following commands were used:
                                          
    {cmds}
    
    Analyze the command according to MITRE ATT&CK.
    """).format(task=task, context=context, result=result, cmds=cmds)

    return llm.with_structured_output(Task).invoke(prompt)

def tool_call_analysis():
    prompt = PromptTemplate.from_template("""You executed the following command:

    `{cmd}`

    which yielded the following result:

    ```
    {result}
    ```

    Analyze the command according to MITRE ATT&CK.
    """).format(cmd=data['cmd'], result=data['result'])

    result = llm.with_structured_output(CmdResult).invoke(prompt)
    console.print(Pretty(result))

def init_tool_calls():
    return {
        'round_done': False,
        'llm_counter': 0,
        'execution_counter': 0,
        'duration': 0,
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'cached_tokens': 0,
        'reasoning_tokens': 0,
        'cmds': {},
        'result': '',
        'out_of_rounds': False
    }


strat_update = None
next_tast = None
tool_calls = None

xslx_path = f"{Path(sys.argv[1]).stem}.xlsx"

print(f"Writing output into {xslx_path}")

workbook = xlsxwriter.Workbook(xslx_path)
worksheet = workbook.add_worksheet()
row = 2

worksheet.write_row(0, 0, ['Update Strategy'])
worksheet.write_row(0, 8, ['Next Task'])
worksheet.write_row(0, 17, ['Executed Commands'])
worksheet.write_row(0, 27, ['Human Analysis'])
worksheet.write_row(0, 36, ['LLM-derived Classification'])

worksheet.write_row(1, 0, [
    'timestamp',
    'model',
    'duration',
    'prompt_tokens',
    'completion_tokens',
    'reasoning_tokens',
    'cached_tokens',
    'result',
    'timestamp',
    'model',
    'duration',
    'prompt_tokens',
    'completion_tokens',
    'reasoning_tokens',
    'cached_tokens',
    'next_task',
    'next_task_context',
    'llm_counter',
    'duration',
    'prompt_tokens',
    'completion_tokens',
    'cached_tokens',
    'reasoning_tokens',
    'execution_counter',
    'out_of_rounds',
    'executed commands',
    'result',
    'compromised systems/accounts',
    'leads (systems/accounts)',
    'missed leads',
    'not-followed up',
    'problems',
    'repeat-missing-context',
    'repeat-tool-error',
    'tactic',
    'attack',
    'successful',
    'tactic',
    'technique'
])

with open(sys.argv[1], 'r') as file:

    tool_calls = init_tool_calls()
    for line in file:
        j = json.loads(line)

        if j['event'] == 'strategy_update':
            strat_update = {
                'timestamp': j['timestamp'],
                'model': j['costs']['model_name'],
                'duration': j['duration'],
                'prompt_tokens': j['costs']['token_usage']['prompt_tokens'],
                'completion_tokens': j['costs']['token_usage']['completion_tokens'],
                'reasoning_tokens': j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens'],
                'cached_tokens': j['costs']['token_usage']['prompt_tokens_details']['cached_tokens'],
                'result': j['result'] }

            assert(j['costs']['token_usage']['completion_tokens_details']['rejected_prediction_tokens'] == 0)

        if j['event'] == 'strategy_next_task':
            next_task = {
                'timestamp': j['timestamp'],
                'model': j['costs']['model_name'],
                'duration': j['duration'],
                'prompt_tokens': j['costs']['token_usage']['prompt_tokens'],
                'completion_tokens': j['costs']['token_usage']['completion_tokens'],
                'next_task': j['result']['next_step'],
                'reasoning_tokens': j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens'],
                'cached_tokens': j['costs']['token_usage']['prompt_tokens_details']['cached_tokens'],
                'next_task_context': j['result']['next_step_context']
            }
            assert(j['costs']['token_usage']['completion_tokens_details']['rejected_prediction_tokens'] == 0)

        # tool calls timed out
        if j['event'] == 'executor_summary_missing':
            cached_tokens = j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']

            tool_calls['duration'] += j['duration']
            tool_calls['prompt_tokens'] += j['costs']['token_usage']['prompt_tokens']
            tool_calls['completion_tokens'] += j['costs']['token_usage']['completion_tokens']
            tool_calls['reasoning_tokens'] += j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens']
            tool_calls['cached_tokens'] += cached_tokens
            tool_calls['result'] = j['result']
            tool_calls['out_of_rounds'] = True
            tool_calls['round_done'] = True
            assert(j['costs']['token_usage']['completion_tokens_details']['rejected_prediction_tokens'] == 0)

        if j['event'] == 'executor_next_cmds':
            cached_tokens = j['costs']['token_usage']['prompt_tokens_details']['cached_tokens']
            tool_calls['llm_counter'] += 1
            tool_calls['duration'] += j['duration']
            tool_calls['prompt_tokens'] += j['costs']['token_usage']['prompt_tokens']
            tool_calls['completion_tokens'] += j['costs']['token_usage']['completion_tokens']
            tool_calls['reasoning_tokens'] += j['costs']['token_usage']['completion_tokens_details']['reasoning_tokens']
            tool_calls['cached_tokens'] += cached_tokens
            assert(j['costs']['token_usage']['completion_tokens_details']['rejected_prediction_tokens'] == 0)
        
            if j['result']['content'] != '':
                # final tool result
                tool_calls['result'] = j['result']['content']
                tool_calls['out_of_rounds'] = False
                tool_calls['round_done'] = True

        if j['event'] == 'executor_cmd':
            tool_calls['execution_counter'] += 1

            cmd = j['cmd'].split(' ')[0]

            if cmd in tool_calls['cmds']:
                tool_calls['cmds'][cmd] += 1
            else:
                tool_calls['cmds'][cmd] = 1

            data = {
                'timestamp': j['timestamp'],
                'cmd': j['cmd'],
                'cmd_tool': j['cmd'].split(' ')[0],
                'result': j['result'],
            }

        if tool_calls['round_done']:
            console.log("Another Round!")
            console.print(Pretty(strat_update))
            console.print(Pretty(next_task))
            console.print(Pretty(tool_calls))

            cmds = "\n".join(map(lambda x: f"- {x} ({tool_calls['cmds'][x]} times)", tool_calls['cmds'].keys()))
            result = analyze_task(next_task['next_task'], next_task['next_task_context'], tool_calls['result'], cmds)
            console.print(Pretty(result))

            worksheet.write_row(row, 0, [
                strat_update['timestamp'],
                strat_update['model'],
                strat_update['duration'],
                strat_update['prompt_tokens'],
                strat_update['completion_tokens'],
                strat_update['reasoning_tokens'],
                strat_update['cached_tokens'],
                strat_update['result'],
                next_task['timestamp'],
                next_task['model'],
                next_task['duration'],
                next_task['prompt_tokens'],
                next_task['completion_tokens'],
                next_task['reasoning_tokens'],
                next_task['cached_tokens'],
                next_task['next_task'],
                next_task['next_task_context'],
                tool_calls['llm_counter'],
                tool_calls['duration'],
                tool_calls['prompt_tokens'],
                tool_calls['completion_tokens'],
                tool_calls['cached_tokens'],
                tool_calls['reasoning_tokens'],
                tool_calls['execution_counter'],
                tool_calls['out_of_rounds'],
                cmds,
                tool_calls['result'],
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                result.successful,
                result.tactic,
                result.technique
            ])
            row +=1

            tool_calls = init_tool_calls()

workbook.close()