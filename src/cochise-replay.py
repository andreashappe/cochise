#!/usr/bin/python3

import json
import sys

from rich.console import Console
from rich.panel import Panel

console = Console()
with open(sys.argv[1], 'r') as file:
    for line in file:
        j = json.loads(line)

        if j['event'] == 'strategy_update':
            console.print(Panel(j['result'], title="Updated Plan", style='bright_green'))

        if j['event'] == 'strategy_next_task':
            next_task = j['result']['next_step']
            next_task_context = j['result']['next_step_context']
            console.print(Panel(f"# Next Step\n\n{next_task}\n\n# Context\n\n{next_task_context}", title='Next Step'), style='bright_yellow')

        # tool calls timed out
        if j['event'] == 'executor_summary_missing':
            console.print(Panel(j['result'], title="Executor ran out of rounds", style='bright_yellow'))

        if j['event'] == 'executor_next_cmds':
            if j['result']['content'] != '' and len(j['result']['tool_calls']) == 0:
                console.print(Panel(j['result']['content'], title="Executor Result", style='bright_yellow'))
            elif j['result']['content'] != '':
                console.print(Panel(j['result']['content'], title="Executor Result"))
            
            if len(j['result']['tool_calls']) > 0:
                result = "\n".join(list(map(lambda x: f"{x['name']}: {x['args']['command']}", j['result']['tool_calls'])))
                console.print(Panel(result, title="Tool Call(s)"))

        if j['event'] == 'executor_cmd':
            console.print(Panel(j['result'], title=f"Result for {j['cmd']}"), markup=False)
