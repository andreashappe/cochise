#!/usr/bin/python3

import argparse
import json

from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty


def analyze_replay(console, file, output_every_x_ptt=1):

    ptt:int = 0

    for line in file:
        j = json.loads(line)

        if 'result' in j:
            result = j['result']

        match j['event']:
            case 'strategy_update':
                ptt += 1
                if ptt >= output_every_x_ptt:
                    console.print(Panel(result, title="Updated Plan", style='bright_green'))
                    ptt = 0
            case 'strategy_next_task':
                next_task = result['next_step']
                next_task_context = result['next_step_context']
                console.print(Panel(f"# Next Step\n\n{next_task}\n\n# Context\n\n{next_task_context}", title='Next Step'), style='bright_yellow')
            case 'executor_summary_missing':
                console.print(Panel(result, title="Executor ran out of rounds", style='bright_yellow'))
            case 'executor_next_cmds':
                if result['content'] != '' and len(result['tool_calls']) == 0:
                    console.print(Panel(result['content'], title="Executor Result", style='bright_yellow'))
                elif result['content'] != '':
                    if isinstance(result['content'], str):
                        console.print(Panel(result['content'], title="Executor Result"))
                    else:
                        console.print(Panel(Pretty(result['content']), title="Executor Result"))
                
                if len(result['tool_calls']) > 0:
                    result = "\n".join(list(map(lambda x: f"{x['name']}: {x['args']['command']}", result['tool_calls'])))
                    console.print(Panel(result, title="Tool Call(s)"))
            case 'executor_cmd':
                console.print(Panel(result, title=f"Result for {j['cmd']}"), markup=False)


if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), help='input file to analyze')
    parser.add_argument('--output-every-x-ptt', type=int, default=1, help='output every x PTTs (default: 1)')
    args = parser.parse_args()

    analyze_replay(console, args.input, args.output_every_x_ptt)