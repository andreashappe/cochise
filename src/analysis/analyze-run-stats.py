#!/usr/bin/python3

import argparse
import json
import math

from pathlib import Path
from rich.console import Console
from rich.table import Table
from dateutil.parser import parse

console = Console()

strat_updates = None
next_tast = None
tool_calls = None

# cmd.split(' ')[0] -> usage count, failed_count
cmds = {}

tools_used_within_run = {}  # tools -> run

runs = {}

def std_dev(dataset):
    # Calculate mean
    length = len(dataset)
    if length == 0:
        return 0, 0
    
    mean = sum(dataset) / length

    # Calculate variance
    squared_diffs = [(x - mean) ** 2 for x in dataset]
    variance = sum(squared_diffs) / length

    return mean, math.sqrt(variance)

round = {}

def create_or_append(run, key, value):

    run = str(run)

    if not run in round:
        round[run] = {}
    
    if not key in round[run]:
        round[run][key] = []

    round[run][key].append(value) 


def analyze_file(filename):


    #with open(filename, 'r') as file:
    if True:
        file = filename
        strat_updates = 0
        executor_decisions = 0
        cmd_calls = 0
        first_timestamp = None
        last_timestamp = None

        exec_counter = 0
        execs = []
        cmd_counter = 0
        exec_cmds = []
        models = []

        # per-run
        cmd_counter = 0

        for line in file:
            j = json.loads(line)
            ts = parse(j["timestamp"])
            if first_timestamp is None:
                first_timestamp = ts
            last_timestamp = ts

            if j['event'] == 'strategy_update':
                strat_updates += 1
                if 'model_name' in j['costs']:
                    model = j['costs']['model_name']
                    if not model in models:
                        models.append(model)
                else:
                    models = ['broken-run']

            if j['event'] == 'strategy_next_task':
                exec_counter = 0

            # tool calls timed out
            if j['event'] == 'executor_summary_missing':
                executor_decisions += 1
                exec_counter += 1

                execs.append(exec_counter)
                exec_cmds.append(cmd_counter)
                exec_counter = 0
                cmd_counter = 0

            if j['event'] == 'executor_next_cmds':
                executor_decisions += 1
                exec_counter += 1

                if len(j['result']['tool_calls']) == 0:
                    execs.append(exec_counter)
                    exec_cmds.append(cmd_counter)
                    exec_counter = 0
                    cmd_counter  = 0

            if j['event'] == 'executor_cmd':
                cmd_calls += 1
                cmd_counter += 1

        mean, variance = std_dev(execs)
        cmd_mean, cmd_var = std_dev(exec_cmds)

        return {
            'filename': Path(filename.name).stem,
            'strat_updates': strat_updates,
            'executor_decisions': executor_decisions,
            'cmd_calls': cmd_calls,
            'executor_commands': execs,
            'executed_commands': exec_cmds,
            'exec_stat_mean': mean,
            'exec_stat_abweich': math.sqrt(variance),
            'cmd_stat_mean': cmd_mean,
            'cmd_stat_abweich': math.sqrt(cmd_var),
            'models': ', '.join(models),
            'duration': (last_timestamp - first_timestamp).total_seconds(),
        }

if __name__=='__main__':

    console = Console()

    parser=argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'), nargs='+', help='input file to analyze')
    args = parser.parse_args()

    table = Table(title=f"Run Information")

    table.add_column("Filename", justify="right", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("Duration", justify="right", style="green")
    table.add_column("Rounds", justify="right", style="green")
    table.add_column("Mean Executor-Calls/Round", justify="right", style="green")
    table.add_column("Dev Executor-Calls/Round", justify="right", style="green")
    table.add_column("Mean Commands/Round", justify="right", style="green")
    table.add_column("Dev Commands/Round", justify="right", style="green")

    valid = 0
    invalid = 0

    for i in args.input:
        result = analyze_file(i)

        if result['models'] != 'broken-run' and result['models'] != '' and result['duration'] > 600 and result['exec_stat_mean'] > 0:
            table.add_row(
                result['filename'],
                result['models'],
                str(result['duration']),
                str(result['strat_updates']),
                str(result['exec_stat_mean']),
                str(result['exec_stat_abweich']),
                str(result['cmd_stat_mean']),
                str(result['cmd_stat_abweich'])
            )
            valid += 1
        else:
            print(f"- {result['filename']} has no valid models or strategy rounds")
            invalid += 1

    console = Console() 
    console.print(table)


    print(f"Valid runs: {valid} Invalid runs: {invalid}")